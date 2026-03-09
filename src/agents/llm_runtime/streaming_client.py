"""Streaming LLM runtime entry point."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Union

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.stream_call_policy import (
    build_stream_kwargs,
    select_stream_llm,
    should_allow_responses_fallback,
)
from src.agents.tool_loop_runner import ToolLoopRunner, ToolLoopState
from src.api.services.file_service import FileService
from src.api.services.model_config_service import ModelConfigService
from src.providers.types import CallMode, TokenUsage
from src.utils.llm_logger import get_llm_logger

from .context import (
    build_context_info_event,
    build_context_plan,
    context_segment_to_system_content,
    estimate_langchain_messages_tokens,
    filter_messages_by_context_boundary,
    get_context_limit,
    trim_to_context_limit,
)
from .messages import convert_to_langchain_messages
from .params import build_llm_request_params
from .reasoning import ReasoningDecision, log_reasoning_decision, resolve_reasoning_decision

logger = logging.getLogger(__name__)

ModelServiceFactory = Callable[[], ModelConfigService]
LoggerFactory = Callable[[], Any]
ToolExecutor = Callable[[str, Dict[str, Any]], Union[Optional[str], Awaitable[Optional[str]]]]


@dataclass(frozen=True)
class StreamingRuntime:
    """Resolved model runtime for one stream invocation."""

    llm_logger: Any
    model_service: Any
    model_config: Any
    provider_config: Any
    capabilities: Any
    adapter: Any
    llm: Any
    actual_model_id: str
    effective_call_mode: CallMode
    allow_responses_fallback: bool
    request_params: Dict[str, Any]
    reasoning_decision: ReasoningDecision


def _resolve_streaming_runtime(
    *,
    model_id: Optional[str],
    session_id: str,
    temperature: Optional[float],
    max_tokens: Optional[int],
    top_p: Optional[float],
    top_k: Optional[int],
    frequency_penalty: Optional[float],
    presence_penalty: Optional[float],
    reasoning_effort: Optional[str],
    model_service_factory: ModelServiceFactory,
    llm_logger_factory: LoggerFactory,
) -> StreamingRuntime:
    llm_logger = llm_logger_factory()
    model_service = model_service_factory()
    model_config, provider_config = model_service.get_model_and_provider_sync(model_id)
    capabilities = model_service.get_merged_capabilities(model_config, provider_config)

    adapter = model_service.get_adapter_for_provider(provider_config)
    resolved_call_mode = model_service.resolve_effective_call_mode(provider_config)
    effective_call_mode = (
        resolved_call_mode
        if isinstance(resolved_call_mode, CallMode)
        else CallMode.AUTO
    )
    allow_responses_fallback = should_allow_responses_fallback(effective_call_mode)

    reasoning_decision = resolve_reasoning_decision(
        capabilities=capabilities,
        reasoning_effort=reasoning_effort,
        model_id=model_config.id,
    )
    reasoning_controls = getattr(capabilities, "reasoning_controls", None)

    api_key = model_service.resolve_provider_api_key_sync(provider_config)
    extra_params: Dict[str, Any] = {}
    for param_name, param_value in {
        "max_tokens": max_tokens,
        "top_p": top_p,
        "top_k": top_k,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
    }.items():
        if param_value is not None:
            extra_params[param_name] = param_value

    temperature_value = 0.7 if temperature is None else temperature
    request_params = build_llm_request_params(
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        top_k=top_k,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
    )
    actual_model_id = f"{provider_config.id}:{model_config.id}"

    log_reasoning_decision(
        session_id=session_id,
        provider_id=provider_config.id,
        model_id=model_config.id,
        call_mode=effective_call_mode.value,
        capabilities=capabilities,
        reasoning_controls=reasoning_controls,
        decision=reasoning_decision,
    )

    llm = adapter.create_llm(
        model=model_config.id,
        base_url=provider_config.base_url,
        api_key=api_key,
        temperature=temperature_value,
        streaming=True,
        call_mode=effective_call_mode.value,
        requires_interleaved_thinking=getattr(capabilities, "requires_interleaved_thinking", False),
        thinking_enabled=reasoning_decision.thinking_enabled,
        reasoning_option=reasoning_decision.effective_reasoning_option,
        reasoning_effort=reasoning_decision.effective_reasoning_effort,
        disable_thinking=reasoning_decision.disable_thinking,
        **extra_params,
    )

    return StreamingRuntime(
        llm_logger=llm_logger,
        model_service=model_service,
        model_config=model_config,
        provider_config=provider_config,
        capabilities=capabilities,
        adapter=adapter,
        llm=llm,
        actual_model_id=actual_model_id,
        effective_call_mode=effective_call_mode,
        allow_responses_fallback=allow_responses_fallback,
        request_params=request_params,
        reasoning_decision=reasoning_decision,
    )


async def call_llm_stream(
    messages: List[Dict[str, str]],
    session_id: str = "unknown",
    model_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
    context_segments: Optional[Dict[str, Optional[str]]] = None,
    max_rounds: Optional[int] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    reasoning_effort: Optional[str] = None,
    file_service: Optional[FileService] = None,
    tools: Optional[List] = None,
    tool_executor: Optional[ToolExecutor] = None,
    model_service_factory: ModelServiceFactory = ModelConfigService,
    llm_logger_factory: LoggerFactory = get_llm_logger,
) -> AsyncIterator[Union[str, Dict[str, Any]]]:
    """Streaming LLM call, yielding text chunks and final metadata events."""
    runtime = _resolve_streaming_runtime(
        model_id=model_id,
        session_id=session_id,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        top_k=top_k,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        reasoning_effort=reasoning_effort,
        model_service_factory=model_service_factory,
        llm_logger_factory=llm_logger_factory,
    )

    print(f"[LLM] Preparing streaming call (model: {runtime.actual_model_id})")
    print(f"      Call mode: {runtime.effective_call_mode.value}")
    print(f"      History messages: {len(messages)}")
    if system_prompt:
        print(f"      Using system prompt: {system_prompt[:50]}...")
    if max_rounds:
        if max_rounds == -1:
            print("      Round limit: unlimited")
        else:
            print(f"      Max rounds: {max_rounds}")
    if runtime.reasoning_decision.disable_thinking:
        print("      Thinking mode: forced off")
    elif runtime.reasoning_decision.thinking_enabled:
        option_for_log = (
            runtime.reasoning_decision.effective_reasoning_option
            or runtime.reasoning_decision.effective_reasoning_effort
        )
        if option_for_log:
            print(f"      Thinking mode: enabled (option: {option_for_log})")
        else:
            print("      Thinking mode: enabled")
    logger.info(
        "Preparing streaming LLM call (model: %s), messages: %s",
        runtime.actual_model_id,
        len(messages),
    )

    filtered_messages, summary_content = filter_messages_by_context_boundary(messages)
    if len(filtered_messages) < len(messages):
        print(f"[CONTEXT] Filtered messages: {len(messages)} -> {len(filtered_messages)}")
        logger.info("Context filtered: %s -> %s messages", len(messages), len(filtered_messages))
        if summary_content:
            print(f"[CONTEXT] Summary context injected ({len(summary_content)} chars)")
            logger.info("Summary context injected: %s chars", len(summary_content))

    max_input_tokens, context_window = get_context_limit(
        llm=runtime.llm,
        capabilities=runtime.capabilities,
    )
    context_plan = build_context_plan(
        messages=filtered_messages,
        system_prompt=system_prompt,
        context_segments=context_segments,
        summary_content=summary_content,
        max_rounds=max_rounds,
        context_budget_tokens=max_input_tokens,
    )

    langchain_messages = [
        SystemMessage(content=context_segment_to_system_content(segment.name, segment.content))
        for segment in context_plan.system_segments
    ]

    if file_service:
        converted_messages = await convert_to_langchain_messages(
            context_plan.chat_messages,
            session_id,
            file_service,
        )
        langchain_messages.extend(converted_messages)
        for index, msg in enumerate(context_plan.chat_messages):
            attachments = msg.get("attachments", [])
            has_images = any(att.get("mime_type", "").startswith("image/") for att in attachments)
            role = msg.get("role", "unknown")
            content_preview = msg["content"][:50] if msg.get("content") else ""
            if has_images:
                print(f"      Message {index + 1}: {role} - {content_preview}... [with images]")
            else:
                print(f"      Message {index + 1}: {role} - {content_preview}...")
    else:
        for index, msg in enumerate(context_plan.chat_messages):
            if msg.get("role") == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
                print(f"      Message {index + 1}: user - {msg['content'][:50]}...")
            elif msg.get("role") == "assistant":
                langchain_messages.append(AIMessage(content=msg["content"]))
                print(f"      Message {index + 1}: assistant - {msg['content'][:50]}...")

    langchain_messages = trim_to_context_limit(langchain_messages, max_input_tokens)
    estimated_prompt_tokens = estimate_langchain_messages_tokens(langchain_messages)

    yield build_context_info_event(
        context_plan=context_plan,
        context_budget=max_input_tokens,
        context_window=context_window,
        estimated_prompt_tokens=estimated_prompt_tokens,
    )

    llm_for_call = runtime.llm
    if tools:
        try:
            llm_for_call = runtime.llm.bind_tools(tools)
            print(f"[TOOLS] Bound {len(tools)} tools to LLM")
            logger.info("Bound %s tools to LLM", len(tools))
        except Exception as exc:
            logger.warning("Failed to bind tools: %s, proceeding without tools", exc)
            llm_for_call = runtime.llm
            tools = None

    try:
        print(f"[LLM] Streaming {len(langchain_messages)} messages to LLM API...")
        logger.info("Streaming LLM API call...")

        full_response = ""
        full_reasoning = ""
        final_usage: Optional[TokenUsage] = None

        latest_user_text = ""
        for raw_msg in reversed(messages):
            if str(raw_msg.get("role", "")).strip().lower() == "user":
                latest_user_text = str(raw_msg.get("content") or "")
                break

        tool_names = {
            str(getattr(tool, "name", "") or "").strip()
            for tool in (tools or [])
            if str(getattr(tool, "name", "") or "").strip()
        }
        max_tool_rounds = ToolLoopRunner.resolve_max_tool_rounds(
            tool_names=tool_names,
            latest_user_text=latest_user_text,
            default_max_tool_rounds=3,
        )
        tool_loop_runner = ToolLoopRunner(max_tool_rounds=max_tool_rounds)
        tool_loop_state = ToolLoopState(
            current_messages=list(langchain_messages),
            web_research_enabled=bool(tool_names.intersection({"web_search", "read_webpage"})),
            max_tool_rounds=max_tool_rounds,
        )
        tool_loop_state.evidence_intent = tool_loop_runner.detect_evidence_intent(latest_user_text)

        while True:
            in_thinking_phase = False
            thinking_ended = False
            thinking_start_time: Optional[float] = None
            round_content = ""
            round_reasoning = ""
            round_reasoning_details: Any = None
            merged_chunk = None

            active_llm = select_stream_llm(
                llm=runtime.llm,
                llm_for_tools=llm_for_call,
                tools_enabled=bool(tools),
                force_finalize_without_tools=tool_loop_state.force_finalize_without_tools,
            )
            stream_kwargs = build_stream_kwargs(
                allow_responses_fallback=runtime.allow_responses_fallback,
            )

            async for chunk in runtime.adapter.stream(
                active_llm,
                tool_loop_state.current_messages,
                **stream_kwargs,
            ):
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    final_usage = chunk_usage

                if chunk.thinking and not runtime.reasoning_decision.disable_thinking:
                    full_reasoning += chunk.thinking
                    round_reasoning += chunk.thinking
                    if not in_thinking_phase:
                        in_thinking_phase = True
                        thinking_start_time = time.time()
                        yield "<think>"
                    yield chunk.thinking

                if chunk.content:
                    if in_thinking_phase and not thinking_ended:
                        thinking_ended = True
                        duration_ms = int((time.time() - thinking_start_time) * 1000) if thinking_start_time else 0
                        yield "</think>"
                        yield {"type": "thinking_duration", "duration_ms": duration_ms}
                    round_content += chunk.content
                    yield chunk.content

                if chunk.raw is not None:
                    try:
                        merged_chunk = chunk.raw if merged_chunk is None else merged_chunk + chunk.raw
                    except Exception:
                        pass

            if merged_chunk is not None:
                extracted_usage = TokenUsage.extract_from_chunk(merged_chunk)
                if extracted_usage and final_usage is None:
                    final_usage = extracted_usage
                if not runtime.reasoning_decision.disable_thinking and not round_reasoning:
                    merged_kwargs = getattr(merged_chunk, "additional_kwargs", None) or {}
                    if isinstance(merged_kwargs, dict):
                        merged_reasoning = merged_kwargs.get("reasoning_content")
                        if isinstance(merged_reasoning, str) and merged_reasoning:
                            round_reasoning = merged_reasoning
                            full_reasoning += merged_reasoning
                merged_kwargs = getattr(merged_chunk, "additional_kwargs", None) or {}
                if isinstance(merged_kwargs, dict):
                    merged_reasoning_details = merged_kwargs.get("reasoning_details")
                    if merged_reasoning_details is not None:
                        round_reasoning_details = merged_reasoning_details

            round_tool_calls = tool_loop_runner.extract_tool_calls(
                merged_chunk,
                tools_enabled=bool(tools),
                force_finalize_without_tools=tool_loop_state.force_finalize_without_tools,
            )

            if in_thinking_phase and not thinking_ended:
                duration_ms = int((time.time() - thinking_start_time) * 1000) if thinking_start_time else 0
                yield "</think>"
                yield {"type": "thinking_duration", "duration_ms": duration_ms}

            full_response += round_content

            if tool_loop_runner.should_request_read_compensation(
                tool_loop_state,
                round_tool_calls=round_tool_calls,
            ):
                if round_content and full_response.endswith(round_content):
                    full_response = full_response[:-len(round_content)]
                print("[TOOLS] Evidence request detected, asking model to call read_knowledge before final answer")
                logger.info("Injecting read_knowledge compensation prompt for evidence-focused request")
                tool_loop_runner.apply_read_compensation_prompt(tool_loop_state)
                continue

            if tool_loop_runner.should_request_web_read_compensation(
                tool_loop_state,
                round_tool_calls=round_tool_calls,
            ):
                if round_content and full_response.endswith(round_content):
                    full_response = full_response[:-len(round_content)]
                print("[TOOLS] Web research needs a webpage read before final answer")
                logger.info("Injecting read_webpage compensation prompt for web research request")
                tool_loop_runner.apply_web_read_compensation_prompt(tool_loop_state)
                continue

            if tool_loop_runner.should_finish_round(
                tool_loop_state,
                round_tool_calls=round_tool_calls,
                tools_enabled=bool(tools),
            ):
                break

            if tool_loop_runner.advance_round_or_force_finalize(
                tool_loop_state,
                round_content=round_content,
                round_reasoning=round_reasoning,
                round_reasoning_details=round_reasoning_details,
            ):
                print(f"[TOOLS] Max tool rounds ({tool_loop_runner.max_tool_rounds}) reached, stopping")
                logger.warning("Max tool call rounds reached")
                continue

            print(f"[TOOLS] Round {tool_loop_state.tool_round}: executing {len(round_tool_calls)} tool(s)")
            logger.info(
                "Tool call round %s: %s",
                tool_loop_state.tool_round,
                [tc["name"] for tc in round_tool_calls],
            )

            yield tool_loop_runner.build_tool_calls_event(round_tool_calls)

            tool_results = await tool_loop_runner.execute_tool_calls(
                round_tool_calls,
                tool_executor=tool_executor,
            )
            tool_loop_runner.record_round_activity(
                tool_loop_state,
                round_tool_calls=round_tool_calls,
                tool_results=tool_results,
            )
            for tool_result in tool_results:
                print(f"[TOOLS]   {tool_result['name']} -> {tool_result['result'][:100]}")

            yield tool_loop_runner.build_tool_results_event(tool_results)
            tool_loop_runner.append_round_with_tool_results(
                tool_loop_state,
                round_content=round_content,
                round_tool_calls=round_tool_calls,
                tool_results=tool_results,
                round_reasoning=round_reasoning,
                round_reasoning_details=round_reasoning_details,
            )

        if tool_loop_runner.should_inject_fallback_answer(tool_loop_state, full_response):
            injected = tool_loop_runner.build_fallback_answer(tool_loop_state)
            if full_response.strip():
                injected = f"\n\n{injected}"
            full_response += injected
            tool_loop_state.tool_finalize_reason = "fallback_empty_answer"
            yield injected

        yield tool_loop_runner.build_tool_diagnostics_event(tool_loop_state)

        if final_usage:
            yield {"type": "usage", "usage": final_usage}

        print(f"[OK] LLM streaming complete, total length: {len(full_response)} chars")
        if full_reasoning:
            print(f"[THINK] Reasoning content length: {len(full_reasoning)} chars")
        if final_usage:
            print(f"[USAGE] Tokens: {final_usage.prompt_tokens} in / {final_usage.completion_tokens} out")
        logger.info("Streaming complete: %s chars", len(full_response))

        response_msg = AIMessage(content=full_response)
        log_extra_params: Dict[str, Any] = {
            "request_params": runtime.request_params,
            "call_mode": runtime.effective_call_mode.value,
            "responses_fallback_enabled": runtime.allow_responses_fallback,
        }
        if runtime.reasoning_decision.disable_thinking:
            log_extra_params["thinking_enabled"] = False
            log_extra_params["reasoning_mode"] = "none"
        elif runtime.reasoning_decision.thinking_enabled:
            log_extra_params["thinking_enabled"] = True
            if runtime.reasoning_decision.effective_reasoning_option:
                log_extra_params["reasoning_option"] = runtime.reasoning_decision.effective_reasoning_option
            if runtime.reasoning_decision.effective_reasoning_effort:
                log_extra_params["reasoning_effort"] = runtime.reasoning_decision.effective_reasoning_effort
        if full_reasoning:
            log_extra_params["reasoning_content"] = full_reasoning
        if final_usage:
            log_extra_params["usage"] = final_usage.model_dump()

        runtime.llm_logger.log_interaction(
            session_id=session_id,
            messages_sent=langchain_messages,
            response_received=response_msg,
            model=runtime.actual_model_id,
            extra_params=log_extra_params,
        )
        print("[LOG] Streaming LLM interaction logged")
    except Exception as exc:
        print(f"[ERROR] LLM streaming API call failed: {str(exc)}")
        logger.error("Streaming API call failed: %s", str(exc), exc_info=True)
        runtime.llm_logger.log_error(session_id, exc, context="LLM Stream API call")
        raise
