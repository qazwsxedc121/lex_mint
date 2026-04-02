"""Streaming LLM runtime entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from src.infrastructure.config.model_config_service import ModelConfigService
from src.infrastructure.files.file_service import FileService
from src.llm_runtime.stream_call_policy import (
    build_stream_kwargs,
    should_allow_responses_fallback,
)
from src.llm_runtime.tool_loop_runtime import (
    ToolLoopRoundResult,
    bind_tools_for_tool_loop,
    build_tool_loop_state,
    decide_tool_loop_branch,
    execute_tool_loop_round,
    finalize_tool_loop,
    resolve_active_stream_llm,
    stream_tool_loop_round,
)
from src.providers.types import CallMode, TokenUsage
from src.utils.llm_logger import get_llm_logger

from .params import build_llm_request_params
from .reasoning import ReasoningDecision, log_reasoning_decision, resolve_reasoning_decision
from .stream_input import prepare_stream_input

logger = logging.getLogger(__name__)

ModelServiceFactory = Callable[[], ModelConfigService]
LoggerFactory = Callable[[], Any]
ToolExecutor = Callable[[str, dict[str, Any]], str | None | Awaitable[str | None]]


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
    request_params: dict[str, Any]
    reasoning_decision: ReasoningDecision


def _resolve_streaming_runtime(
    *,
    model_id: str | None,
    session_id: str,
    temperature: float | None,
    max_tokens: int | None,
    top_p: float | None,
    top_k: int | None,
    frequency_penalty: float | None,
    presence_penalty: float | None,
    reasoning_effort: str | None,
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
        resolved_call_mode if isinstance(resolved_call_mode, CallMode) else CallMode.AUTO
    )
    allow_responses_fallback = should_allow_responses_fallback(effective_call_mode)

    reasoning_decision = resolve_reasoning_decision(
        capabilities=capabilities,
        reasoning_effort=reasoning_effort,
        model_id=model_config.id,
    )
    reasoning_controls = getattr(capabilities, "reasoning_controls", None)

    api_key = model_service.resolve_provider_api_key_sync(provider_config)
    extra_params: dict[str, Any] = {}
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


def _log_stream_preparation(
    *,
    runtime: StreamingRuntime,
    messages: list[dict[str, str]],
    system_prompt: str | None,
    max_rounds: int | None,
) -> None:
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


def _latest_user_text(messages: list[dict[str, str]]) -> str:
    for raw_msg in reversed(messages):
        if str(raw_msg.get("role", "")).strip().lower() == "user":
            return str(raw_msg.get("content") or "")
    return ""


def _build_log_extra_params(
    *,
    runtime: StreamingRuntime,
    full_reasoning: str,
    final_usage: TokenUsage | None,
) -> dict[str, Any]:
    log_extra_params: dict[str, Any] = {
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
            log_extra_params["reasoning_option"] = (
                runtime.reasoning_decision.effective_reasoning_option
            )
        if runtime.reasoning_decision.effective_reasoning_effort:
            log_extra_params["reasoning_effort"] = (
                runtime.reasoning_decision.effective_reasoning_effort
            )
    if full_reasoning:
        log_extra_params["reasoning_content"] = full_reasoning
    if final_usage:
        log_extra_params["usage"] = final_usage.model_dump()
    return log_extra_params


def _log_stream_completion(
    *,
    runtime: StreamingRuntime,
    session_id: str,
    langchain_messages: list[BaseMessage],
    full_response: str,
    full_reasoning: str,
    final_usage: TokenUsage | None,
) -> None:
    print(f"[OK] LLM streaming complete, total length: {len(full_response)} chars")
    if full_reasoning:
        print(f"[THINK] Reasoning content length: {len(full_reasoning)} chars")
    if final_usage:
        print(
            f"[USAGE] Tokens: {final_usage.prompt_tokens} in / {final_usage.completion_tokens} out"
        )
    logger.info("Streaming complete: %s chars", len(full_response))

    runtime.llm_logger.log_interaction(
        session_id=session_id,
        messages_sent=langchain_messages,
        response_received=AIMessage(content=full_response),
        model=runtime.actual_model_id,
        extra_params=_build_log_extra_params(
            runtime=runtime,
            full_reasoning=full_reasoning,
            final_usage=final_usage,
        ),
    )
    print("[LOG] Streaming LLM interaction logged")


async def call_llm_stream(
    messages: list[dict[str, str]],
    session_id: str = "unknown",
    model_id: str | None = None,
    system_prompt: str | None = None,
    context_segments: dict[str, str | None] | None = None,
    max_rounds: int | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
    reasoning_effort: str | None = None,
    file_service: FileService | None = None,
    tools: list | None = None,
    tool_executor: ToolExecutor | None = None,
    model_service_factory: ModelServiceFactory = ModelConfigService,
    llm_logger_factory: LoggerFactory = get_llm_logger,
) -> AsyncIterator[str | dict[str, Any]]:
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
    _log_stream_preparation(
        runtime=runtime,
        messages=messages,
        system_prompt=system_prompt,
        max_rounds=max_rounds,
    )
    prepared_input = await prepare_stream_input(
        runtime=runtime,
        messages=messages,
        session_id=session_id,
        system_prompt=system_prompt,
        context_segments=context_segments,
        max_rounds=max_rounds,
        file_service=file_service,
    )
    langchain_messages = prepared_input.langchain_messages
    yield prepared_input.context_event

    try:
        print(f"[LLM] Streaming {len(langchain_messages)} messages to LLM API...")
        logger.info("Streaming LLM API call...")

        full_response = ""
        full_reasoning = ""
        final_usage: TokenUsage | None = None
        latest_user_text = _latest_user_text(messages)
        bound_tools = bind_tools_for_tool_loop(
            llm=runtime.llm,
            llm_tools=tools,
            warning_message="Failed to bind tools",
        )
        tool_loop_runner, tool_loop_state = build_tool_loop_state(
            langchain_messages=langchain_messages,
            latest_user_text=latest_user_text,
            tool_names=bound_tools.tool_names,
        )

        while True:
            active_llm = resolve_active_stream_llm(
                runtime=runtime,
                llm_for_tools=bound_tools.llm_for_tools,
                tools_enabled=bound_tools.tools_enabled,
                tool_loop_state=tool_loop_state,
            )
            stream_kwargs = build_stream_kwargs(
                allow_responses_fallback=runtime.allow_responses_fallback,
            )
            round_result: ToolLoopRoundResult | None = None
            async for chunk in stream_tool_loop_round(
                runtime=runtime,
                active_llm=active_llm,
                current_messages=tool_loop_state.current_messages,
                stream_kwargs=stream_kwargs,
            ):
                if isinstance(chunk, ToolLoopRoundResult):
                    round_result = chunk
                    continue
                yield chunk
            if round_result is None:
                round_result = ToolLoopRoundResult("", "", None, final_usage, None)
            if round_result.final_usage is not None:
                final_usage = round_result.final_usage
            if round_result.round_reasoning:
                full_reasoning += round_result.round_reasoning

            full_response += round_result.round_content
            decision = decide_tool_loop_branch(
                tool_loop_runner=tool_loop_runner,
                tool_loop_state=tool_loop_state,
                round_result=round_result,
                full_response=full_response,
                tools_enabled=bound_tools.tools_enabled,
            )
            full_response = decision.full_response
            round_tool_calls = decision.round_tool_calls
            if decision.branch == "continue":
                continue

            if decision.branch == "finalize":
                break

            print(
                f"[TOOLS] Round {tool_loop_state.tool_round}: executing {len(round_tool_calls)} tool(s)"
            )
            logger.info(
                "Tool call round %s: %s",
                tool_loop_state.tool_round,
                [tc["name"] for tc in round_tool_calls],
            )

            yield tool_loop_runner.build_tool_calls_event(round_tool_calls)

            tool_results = await execute_tool_loop_round(
                tool_loop_runner=tool_loop_runner,
                tool_loop_state=tool_loop_state,
                round_tool_calls=round_tool_calls,
                tool_executor=tool_executor,
                round_content=round_result.round_content,
                round_reasoning=round_result.round_reasoning,
                round_reasoning_details=round_result.round_reasoning_details,
            )
            for tool_result in tool_results:
                print(f"[TOOLS]   {tool_result['name']} -> {tool_result['result'][:100]}")

            yield tool_loop_runner.build_tool_results_event(tool_results)

        finalize_result = finalize_tool_loop(
            tool_loop_runner=tool_loop_runner,
            tool_loop_state=tool_loop_state,
            full_response=full_response,
        )
        full_response = finalize_result.full_response
        if finalize_result.injected_text:
            yield finalize_result.injected_text
        yield finalize_result.diagnostics_event

        if final_usage:
            yield {"type": "usage", "usage": final_usage}
        _log_stream_completion(
            runtime=runtime,
            session_id=session_id,
            langchain_messages=langchain_messages,
            full_response=full_response,
            full_reasoning=full_reasoning,
            final_usage=final_usage,
        )
    except Exception as exc:
        print(f"[ERROR] LLM streaming API call failed: {str(exc)}")
        logger.error("Streaming API call failed: %s", str(exc), exc_info=True)
        runtime.llm_logger.log_error(session_id, exc, context="LLM Stream API call")
        raise
