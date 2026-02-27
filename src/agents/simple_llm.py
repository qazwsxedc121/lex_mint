"""Simple LLM call service - without LangGraph"""

import time
import json
import logging
from typing import List, Dict, Any, AsyncIterator, Optional, Union, Tuple, Callable, Awaitable
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage, trim_messages

from src.utils.llm_logger import get_llm_logger
from src.api.services.model_config_service import ModelConfigService
from src.api.services.file_service import FileService
from src.agents.stream_call_policy import (
    build_stream_kwargs,
    select_stream_llm,
    should_allow_responses_fallback,
)
from src.agents.tool_loop_runner import ToolLoopRunner, ToolLoopState
from src.providers.types import CallMode, TokenUsage

logger = logging.getLogger(__name__)

# --- Context trimming constants ---
DEFAULT_CONTEXT_LENGTH = 4096
DEFAULT_OUTPUT_RESERVE_RATIO = 0.25   # config-based: reserve 25% for output
MIN_OUTPUT_RESERVE = 1024
MAX_OUTPUT_RESERVE = 32000


def _calculate_output_reserve(context_length: int, from_profile: bool) -> int:
    """Calculate how many tokens to reserve for model output.

    Args:
        context_length: Total context window size.
        from_profile: True if context_length came from llm.profile
            (max_input_tokens already excludes output), False if from config
            (context_length is total window).

    Returns:
        Number of tokens to reserve for output.
    """
    if from_profile:
        # profile's max_input_tokens already excludes output budget,
        # only apply a small 5% safety margin
        return int(context_length * 0.05)
    # config-based: reserve 25%, clamped to [1024, 32000]
    reserve = int(context_length * DEFAULT_OUTPUT_RESERVE_RATIO)
    return max(MIN_OUTPUT_RESERVE, min(MAX_OUTPUT_RESERVE, reserve))


def _get_context_limit(llm, capabilities) -> Tuple[int, int]:
    """Determine the max input tokens allowed before calling the LLM.

    Priority:
      1. llm.profile['max_input_tokens'] (LangChain built-in, zero cost)
      2. capabilities.context_length (from models_config.yaml)
      3. DEFAULT_CONTEXT_LENGTH (absolute fallback)

    Returns:
        Tuple of (usable input token budget, raw context window size).
    """
    # Priority 1: LangChain profile
    profile_limit = None
    try:
        profile = getattr(llm, "profile", None)
        if profile and isinstance(profile, dict):
            profile_limit = profile.get("max_input_tokens")
    except Exception:
        pass

    if profile_limit and isinstance(profile_limit, int) and profile_limit > 0:
        reserve = _calculate_output_reserve(profile_limit, from_profile=True)
        budget = profile_limit - reserve
        logger.info(
            f"[CONTEXT] Using profile max_input_tokens={profile_limit}, "
            f"reserve={reserve}, budget={budget}"
        )
        return budget, profile_limit

    # Priority 2: capabilities from config
    config_limit = getattr(capabilities, "context_length", None)
    if config_limit and isinstance(config_limit, int) and config_limit > DEFAULT_CONTEXT_LENGTH:
        reserve = _calculate_output_reserve(config_limit, from_profile=False)
        budget = config_limit - reserve
        logger.info(
            f"[CONTEXT] Using config context_length={config_limit}, "
            f"reserve={reserve}, budget={budget}"
        )
        return budget, config_limit

    # Priority 3: absolute fallback
    reserve = _calculate_output_reserve(DEFAULT_CONTEXT_LENGTH, from_profile=False)
    budget = DEFAULT_CONTEXT_LENGTH - reserve
    logger.info(
        f"[CONTEXT] Using default context_length={DEFAULT_CONTEXT_LENGTH}, "
        f"reserve={reserve}, budget={budget}"
    )
    return budget, DEFAULT_CONTEXT_LENGTH


def _trim_to_context_limit(
    messages: List[BaseMessage], max_input_tokens: int
) -> List[BaseMessage]:
    """Trim messages to fit within the token budget using approximate counting.

    Args:
        messages: LangChain messages (may include a leading SystemMessage).
        max_input_tokens: Maximum input tokens allowed.

    Returns:
        Trimmed message list (system message always preserved).
    """
    trimmed = trim_messages(
        messages,
        max_tokens=max_input_tokens,
        strategy="last",
        token_counter="approximate",
        include_system=True,
        start_on="human",
    )
    if len(trimmed) < len(messages):
        logger.info(
            f"[TRIM] Messages trimmed: {len(messages)} -> {len(trimmed)} "
            f"(budget: {max_input_tokens} tokens)"
        )
        print(
            f"[TRIM] Messages trimmed to fit context window: "
            f"{len(messages)} -> {len(trimmed)} messages "
            f"(budget: {max_input_tokens} tokens)"
        )
    return trimmed


# Approximate tokens per character ratio (rough heuristic: ~4 chars per token)
_APPROX_CHARS_PER_TOKEN = 4


def _estimate_total_tokens(messages: List[Dict]) -> int:
    """Estimate total token count for raw message dicts.

    Uses actual completion_tokens from assistant message metadata when available,
    falls back to approximate character-based estimation for other messages.

    Args:
        messages: Raw message dicts with role, content, and optional usage metadata.

    Returns:
        Estimated total token count.
    """
    total = 0
    for msg in messages:
        role = msg.get("role", "")
        if role not in ("user", "assistant"):
            continue

        # For assistant messages, prefer recorded token count from usage metadata
        if role == "assistant":
            usage = msg.get("usage")
            if usage and isinstance(usage, dict):
                completion_tokens = usage.get("completion_tokens")
                if completion_tokens and completion_tokens > 0:
                    total += completion_tokens
                    continue

        # Fallback: approximate from content length
        content = msg.get("content", "")
        total += max(1, len(content) // _APPROX_CHARS_PER_TOKEN)

    return total


def _build_llm_request_params(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
) -> Dict[str, Any]:
    """Build sanitized request params for logging (no secrets)."""
    params: Dict[str, Any] = {
        "temperature": 0.7 if temperature is None else temperature
    }
    for key, value in {
        "max_tokens": max_tokens,
        "top_p": top_p,
        "top_k": top_k,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
    }.items():
        if value is not None:
            params[key] = value
    return params


async def convert_to_langchain_messages(
    messages: List[Dict],
    session_id: str,
    file_service: FileService
) -> List[BaseMessage]:
    """Convert messages to LangChain format, supporting multimodal content.

    Args:
        messages: Message list with optional attachments
        session_id: Session ID for locating attachment files
        file_service: File service for reading attachments

    Returns:
        List of LangChain BaseMessage objects
    """
    langchain_messages = []

    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            attachments = msg.get("attachments", [])

            # Check if any attachments are images
            has_images = any(
                att.get("mime_type", "").startswith("image/")
                for att in attachments
            )

            if has_images:
                # Construct multimodal content list
                content_list = []

                # Add text content (if any)
                if msg["content"].strip():
                    content_list.append({
                        "type": "text",
                        "text": msg["content"]
                    })

                # Add images
                for att in attachments:
                    if att.get("mime_type", "").startswith("image/"):
                        # Read image file and Base64 encode
                        image_path = file_service.get_file_path(
                            session_id, i, att["filename"]
                        )
                        if image_path:
                            try:
                                base64_data = await file_service.get_file_as_base64(image_path)
                                content_list.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{att['mime_type']};base64,{base64_data}"
                                    }
                                })
                                logger.info(f"Added image to message: {att['filename']}")
                            except Exception as e:
                                logger.error(f"Failed to read image {att['filename']}: {e}")
                                # Continue without this image

                langchain_messages.append(HumanMessage(content=content_list))
            else:
                # Pure text message (or text files already embedded in content)
                langchain_messages.append(HumanMessage(content=msg["content"]))

        elif msg.get("role") == "assistant":
            langchain_messages.append(AIMessage(content=msg["content"]))

    return langchain_messages


def call_llm(
    messages: List[Dict[str, str]],
    session_id: str = "unknown",
    model_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None
) -> str:
    """
    Direct LLM call without LangGraph.

    Args:
        messages: Message list [{"role": "user/assistant", "content": "..."}]
        session_id: Session ID (for logging)
        model_id: Model ID, if None uses default model

    Returns:
        AI response content
    """
    llm_logger = get_llm_logger()

    # Dynamically get LLM instance
    model_service = ModelConfigService()
    model_config, provider_config = model_service.get_model_and_provider_sync(model_id)
    capabilities = model_service.get_merged_capabilities(model_config, provider_config)
    llm = model_service.get_llm_instance(
        model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        top_k=top_k,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
    )

    # Get actual model ID
    actual_model_id = model_id or model_service.get_llm_instance().model_name
    request_params = _build_llm_request_params(
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        top_k=top_k,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
    )

    print(f"[LLM] Preparing to call LLM (model: {actual_model_id})")
    print(f"      History messages: {len(messages)}")
    logger.info(f"Preparing to call LLM (model: {actual_model_id}), messages: {len(messages)}")

    # === Filter messages after last context boundary ===
    filtered_messages, summary_content = _filter_messages_by_context_boundary(messages)
    if len(filtered_messages) < len(messages):
        print(f"[CONTEXT] Filtered messages: {len(messages)} -> {len(filtered_messages)}")
        logger.info(f"Context filtered: {len(messages)} -> {len(filtered_messages)} messages")

    # Convert message format
    langchain_messages = []
    if system_prompt:
        langchain_messages.append(SystemMessage(content=system_prompt))
    if summary_content:
        langchain_messages.append(SystemMessage(content=f"<compressed_history_summary>\n{summary_content}\n</compressed_history_summary>"))
    for i, msg in enumerate(filtered_messages):
        if msg.get("role") == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
            print(f"      Message {i+1}: user - {msg['content'][:50]}...")
        elif msg.get("role") == "assistant":
            langchain_messages.append(AIMessage(content=msg["content"]))
            print(f"      Message {i+1}: assistant - {msg['content'][:50]}...")

    # === Safety net: trim to context window limit ===
    max_input_tokens, _context_window = _get_context_limit(llm=llm, capabilities=capabilities)
    langchain_messages = _trim_to_context_limit(langchain_messages, max_input_tokens)

    try:
        print(f"[LLM] Sending {len(langchain_messages)} messages to LLM API...")
        logger.info(f"Calling LLM API...")

        # Call LLM (only once!)
        response = llm.invoke(langchain_messages)

        response_content_raw = response.content
        response_content = (
            response_content_raw
            if isinstance(response_content_raw, str)
            else str(response_content_raw or "")
        )
        print(f"[OK] Received LLM response, length: {len(response_content)} chars")
        logger.info(f"Received response: {len(response_content)} chars")

        # Log interaction
        llm_logger.log_interaction(
            session_id=session_id,
            messages_sent=langchain_messages,
            response_received=response,
            model=actual_model_id,
            extra_params={"request_params": request_params}
        )
        print(f"[LOG] LLM interaction logged")

        return response_content

    except Exception as e:
        print(f"[ERROR] LLM API call failed: {str(e)}")
        logger.error(f"API call failed: {str(e)}", exc_info=True)
        llm_logger.log_error(session_id, e, context="LLM API call")
        raise


async def call_llm_stream(
    messages: List[Dict[str, str]],
    session_id: str = "unknown",
    model_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
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
    tool_executor: Optional[Callable[[str, Dict[str, Any]], Union[Optional[str], Awaitable[Optional[str]]]]] = None,
) -> AsyncIterator[Union[str, Dict[str, Any]]]:
    """
    Streaming LLM call, yields tokens one by one.

    Uses the adapter registry to select appropriate SDK based on provider config,
    instead of text-matching on URLs.

    Args:
        messages: Message list [{"role": "user/assistant", "content": "..."}]
        session_id: Session ID (for logging)
        model_id: Model ID, if None uses default model
        system_prompt: System prompt (optional)
        max_rounds: Max conversation rounds (optional), -1 or None means unlimited
        reasoning_effort: Reasoning mode:
            - "low"/"medium"/"high": enable reasoning with effort
            - "none": force-disable reasoning output
            - "default"/None: do not pass reasoning params
        file_service: File service for reading image attachments (optional)
        tool_executor: Request-scoped tool executor. If provided, called as
            `tool_executor(name, args)` before registry execution. Returning
            None falls back to registry tools.

    Yields:
        String tokens during streaming, or dict with usage info at the end:
        {"type": "usage", "usage": TokenUsage}
    """
    llm_logger = get_llm_logger()

    # Get model and provider configuration
    model_service = ModelConfigService()
    model_config, provider_config = model_service.get_model_and_provider_sync(model_id)

    # Get merged capabilities (provider defaults + model overrides)
    capabilities = model_service.get_merged_capabilities(model_config, provider_config)

    # Get the appropriate adapter via registry (no text matching!)
    adapter = model_service.get_adapter_for_provider(provider_config)
    resolved_call_mode = model_service.resolve_effective_call_mode(provider_config)
    effective_call_mode = (
        resolved_call_mode
        if isinstance(resolved_call_mode, CallMode)
        else CallMode.AUTO
    )
    allow_responses_fallback = should_allow_responses_fallback(effective_call_mode)

    # Determine reasoning behavior from model-native option selection.
    reasoning_mode = (reasoning_effort or "").strip().lower()
    explicit_disable_reasoning = reasoning_mode == "none"
    effective_reasoning_effort: Optional[str] = None
    effective_reasoning_option: Optional[str] = None
    thinking_enabled = False

    reasoning_controls = getattr(capabilities, "reasoning_controls", None)
    reasoning_controls_mode: Optional[str] = None
    if reasoning_controls is not None:
        raw_mode = getattr(reasoning_controls, "mode", None)
        if isinstance(raw_mode, str):
            reasoning_controls_mode = raw_mode.strip().lower()
        else:
            raw_mode_value = getattr(raw_mode, "value", None)
            if isinstance(raw_mode_value, str):
                reasoning_controls_mode = raw_mode_value.strip().lower()

    disable_reasoning_supported = True
    if reasoning_controls is not None:
        raw_disable_supported = getattr(reasoning_controls, "disable_supported", True)
        if isinstance(raw_disable_supported, bool):
            disable_reasoning_supported = raw_disable_supported

    disable_thinking = explicit_disable_reasoning and disable_reasoning_supported
    raw_reasoning_options = getattr(reasoning_controls, "options", []) if reasoning_controls is not None else []
    options_iterable = raw_reasoning_options if isinstance(raw_reasoning_options, list) else []
    allowed_reasoning_options = [
        str(option).strip().lower()
        for option in options_iterable
        if str(option).strip()
    ]

    if explicit_disable_reasoning:
        if not disable_reasoning_supported:
            logger.warning("Reasoning disable is not supported for %s; ignoring 'none'", model_config.id)
        else:
            logger.info(f"Reasoning explicitly disabled for {model_config.id}")
    elif reasoning_mode and reasoning_mode != "default":
        if not capabilities.reasoning:
            logger.warning(
                f"Model {model_config.id} does not support reasoning mode, ignoring reasoning_effort={reasoning_mode}"
            )
        elif allowed_reasoning_options:
            if reasoning_mode in allowed_reasoning_options:
                thinking_enabled = True
                effective_reasoning_option = reasoning_mode
                if reasoning_controls_mode == "enum":
                    effective_reasoning_effort = reasoning_mode
                logger.info(
                    "Thinking mode enabled for %s (%s=%s)",
                    model_config.id,
                    reasoning_controls.param if reasoning_controls else "reasoning",
                    effective_reasoning_option,
                )
            elif (
                reasoning_controls_mode == "toggle"
                and reasoning_mode in {"low", "medium", "high", "minimal"}
            ):
                thinking_enabled = True
                effective_reasoning_option = allowed_reasoning_options[0]
                logger.info(
                    "Mapped legacy reasoning option '%s' to toggle value '%s' for %s",
                    reasoning_mode,
                    effective_reasoning_option,
                    model_config.id,
                )
            else:
                logger.warning(
                    "Unsupported reasoning option '%s' for %s; allowed=%s",
                    reasoning_mode,
                    model_config.id,
                    ",".join(allowed_reasoning_options),
                )
        elif reasoning_mode in {"low", "medium", "high", "minimal"}:
            # Legacy fallback for models without structured controls.
            thinking_enabled = True
            effective_reasoning_option = reasoning_mode
            effective_reasoning_effort = reasoning_mode
            logger.info(
                f"Thinking mode enabled for {model_config.id} (effort: {effective_reasoning_effort})"
            )
        else:
            logger.warning(
                f"Unknown reasoning_effort '{reasoning_mode}', falling back to model default behavior"
            )

    # Get API key
    api_key = model_service.resolve_provider_api_key_sync(provider_config)

    # Build extra params from assistant config (if provided)
    extra_params = {}
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
    request_params = _build_llm_request_params(
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        top_k=top_k,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
    )

    # Create LLM instance via adapter
    llm = adapter.create_llm(
        model=model_config.id,
        base_url=provider_config.base_url,
        api_key=api_key,
        temperature=temperature_value,
        streaming=True,
        call_mode=effective_call_mode.value,
        requires_interleaved_thinking=capabilities.requires_interleaved_thinking,
        thinking_enabled=thinking_enabled,
        reasoning_option=effective_reasoning_option,
        reasoning_effort=effective_reasoning_effort,
        disable_thinking=disable_thinking,
        **extra_params,
    )

    actual_model_id = f"{provider_config.id}:{model_config.id}"

    print(f"[LLM] Preparing streaming call (model: {actual_model_id})")
    print(f"      Call mode: {effective_call_mode.value}")
    print(f"      History messages: {len(messages)}")
    if system_prompt:
        print(f"      Using system prompt: {system_prompt[:50]}...")
    if max_rounds:
        if max_rounds == -1:
            print(f"      Round limit: unlimited")
        else:
            print(f"      Max rounds: {max_rounds}")
    if disable_thinking:
        print("      Thinking mode: forced off")
    elif thinking_enabled:
        option_for_log = effective_reasoning_option or effective_reasoning_effort
        if option_for_log:
            print(f"      Thinking mode: enabled (option: {option_for_log})")
        else:
            print("      Thinking mode: enabled")
    logger.info(f"Preparing streaming LLM call (model: {actual_model_id}), messages: {len(messages)}")

    # === Filter messages after last context boundary (separator or summary) ===
    filtered_messages, summary_content = _filter_messages_by_context_boundary(messages)
    if len(filtered_messages) < len(messages):
        print(f"[CONTEXT] Filtered messages: {len(messages)} -> {len(filtered_messages)}")
        logger.info(f"Context filtered: {len(messages)} -> {len(filtered_messages)} messages")
        if summary_content:
            print(f"[CONTEXT] Summary context injected ({len(summary_content)} chars)")
            logger.info(f"Summary context injected: {len(summary_content)} chars")

    # Convert message format (with multimodal support if file_service provided)
    langchain_messages = []

    # Inject system prompt (if provided)
    if system_prompt:
        langchain_messages.append(SystemMessage(content=system_prompt))

    # Inject summary context as a system message (if previous context was compressed)
    if summary_content:
        langchain_messages.append(SystemMessage(content=f"<compressed_history_summary>\n{summary_content}\n</compressed_history_summary>"))

    # Use multimodal conversion if file_service is available
    if file_service:
        converted_messages = await convert_to_langchain_messages(filtered_messages, session_id, file_service)
        langchain_messages.extend(converted_messages)
        for i, msg in enumerate(filtered_messages):
            # Check if message has image attachments
            attachments = msg.get("attachments", [])
            has_images = any(att.get("mime_type", "").startswith("image/") for att in attachments)
            role = msg.get("role", "unknown")
            content_preview = msg["content"][:50] if msg.get("content") else ""
            if has_images:
                print(f"      Message {i+1}: {role} - {content_preview}... [with images]")
            else:
                print(f"      Message {i+1}: {role} - {content_preview}...")
    else:
        # Fallback to simple text conversion (no image support)
        for i, msg in enumerate(filtered_messages):
            if msg.get("role") == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
                print(f"      Message {i+1}: user - {msg['content'][:50]}...")
            elif msg.get("role") == "assistant":
                langchain_messages.append(AIMessage(content=msg["content"]))
                print(f"      Message {i+1}: assistant - {msg['content'][:50]}...")

    # Truncate by conversation rounds (if specified)
    if max_rounds and max_rounds > 0:
        langchain_messages = _truncate_by_rounds(langchain_messages, max_rounds, system_prompt)
        print(f"      After truncation: {len(langchain_messages)} messages")

    # === Safety net: trim to context window limit ===
    max_input_tokens, context_window = _get_context_limit(llm=llm, capabilities=capabilities)
    langchain_messages = _trim_to_context_limit(langchain_messages, max_input_tokens)

    # Yield context info so frontend can display usage bar
    yield {
        "type": "context_info",
        "context_budget": max_input_tokens,
        "context_window": context_window,
    }

    # Bind tools to LLM if provided
    llm_for_call = llm
    if tools:
        try:
            llm_for_call = llm.bind_tools(tools)
            print(f"[TOOLS] Bound {len(tools)} tools to LLM")
            logger.info(f"Bound {len(tools)} tools to LLM")
        except Exception as e:
            logger.warning(f"Failed to bind tools: {e}, proceeding without tools")
            llm_for_call = llm
            tools = None

    try:
        print(f"[LLM] Streaming {len(langchain_messages)} messages to LLM API...")
        logger.info(f"Streaming LLM API call...")

        # Collect full response for logging
        full_response = ""
        full_reasoning = ""
        final_usage: Optional[TokenUsage] = None

        tool_loop_runner = ToolLoopRunner(max_tool_rounds=3)
        tool_loop_state = ToolLoopState(current_messages=list(langchain_messages))
        latest_user_text = ""
        for raw_msg in reversed(messages):
            if str(raw_msg.get("role", "")).strip().lower() == "user":
                latest_user_text = str(raw_msg.get("content") or "")
                break
        tool_loop_state.evidence_intent = tool_loop_runner.detect_evidence_intent(latest_user_text)

        while True:
            in_thinking_phase = False
            thinking_ended = False
            thinking_start_time: Optional[float] = None
            round_content = ""
            round_reasoning = ""
            round_reasoning_details: Any = None
            round_tool_calls: List[Dict[str, Any]] = []
            # Merge raw LangChain chunks to get complete tool_calls after stream ends
            merged_chunk = None

            # Stream via adapter (unified interface)
            active_llm = select_stream_llm(
                llm=llm,
                llm_for_tools=llm_for_call,
                tools_enabled=bool(tools),
                force_finalize_without_tools=tool_loop_state.force_finalize_without_tools,
            )
            stream_kwargs = build_stream_kwargs(
                allow_responses_fallback=allow_responses_fallback,
            )
            async for chunk in adapter.stream(active_llm, tool_loop_state.current_messages, **stream_kwargs):
                # Prefer adapter-normalized chunk usage when present.
                # Some OpenAI-compatible providers emit cumulative usage per chunk;
                # relying on merged raw chunks can over-count those values.
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    final_usage = chunk_usage

                # Handle thinking/reasoning content
                if chunk.thinking and not disable_thinking:
                    full_reasoning += chunk.thinking
                    round_reasoning += chunk.thinking
                    if not in_thinking_phase:
                        in_thinking_phase = True
                        thinking_start_time = time.time()
                        yield "<think>"
                    yield chunk.thinking

                # Handle regular content
                if chunk.content:
                    if in_thinking_phase and not thinking_ended:
                        thinking_ended = True
                        duration_ms = int((time.time() - thinking_start_time) * 1000) if thinking_start_time else 0
                        yield "</think>"
                        yield {"type": "thinking_duration", "duration_ms": duration_ms}
                    round_content += chunk.content
                    yield chunk.content

                # Merge raw chunks for usage and tool_calls after stream ends
                if chunk.raw is not None:
                    try:
                        merged_chunk = chunk.raw if merged_chunk is None else merged_chunk + chunk.raw
                    except Exception:
                        pass

            # After stream ends: extract usage from merged chunk
            if merged_chunk is not None:
                extracted_usage = TokenUsage.extract_from_chunk(merged_chunk)
                if extracted_usage and final_usage is None:
                    final_usage = extracted_usage
                if not disable_thinking and not round_reasoning:
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

            # After stream ends: extract complete tool_calls from merged chunk
            round_tool_calls = tool_loop_runner.extract_tool_calls(
                merged_chunk,
                tools_enabled=bool(tools),
                force_finalize_without_tools=tool_loop_state.force_finalize_without_tools,
            )

            # Close thinking tag if opened but no content followed
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
                    full_response = full_response[: -len(round_content)]
                print("[TOOLS] Evidence request detected, asking model to call read_knowledge before final answer")
                logger.info("Injecting read_knowledge compensation prompt for evidence-focused request")
                tool_loop_runner.apply_read_compensation_prompt(tool_loop_state)
                continue

            # Finalization pass intentionally disables tools; finish after this round.
            if tool_loop_runner.should_finish_round(
                tool_loop_state,
                round_tool_calls=round_tool_calls,
                tools_enabled=bool(tools),
            ):
                break

            # Tool call loop: execute tools and re-call LLM
            if tool_loop_runner.advance_round_or_force_finalize(
                tool_loop_state,
                round_content=round_content,
                round_reasoning=round_reasoning,
                round_reasoning_details=round_reasoning_details,
            ):
                print(f"[TOOLS] Max tool rounds ({tool_loop_runner.max_tool_rounds}) reached, stopping")
                logger.warning("Max tool call rounds reached")
                round_content = ""
                round_reasoning = ""
                round_tool_calls = []
                continue

            print(f"[TOOLS] Round {tool_loop_state.tool_round}: executing {len(round_tool_calls)} tool(s)")
            logger.info(
                "Tool call round %s: %s",
                tool_loop_state.tool_round,
                [tc["name"] for tc in round_tool_calls],
            )

            # Yield tool_calls event to frontend
            yield tool_loop_runner.build_tool_calls_event(round_tool_calls)

            # Execute tools
            tool_results = await tool_loop_runner.execute_tool_calls(
                round_tool_calls,
                tool_executor=tool_executor,
            )
            tool_loop_runner.record_round_activity(
                tool_loop_state,
                round_tool_calls=round_tool_calls,
                tool_results=tool_results,
            )
            for tr in tool_results:
                print(f"[TOOLS]   {tr['name']} -> {tr['result'][:100]}")

            # Yield tool_results event to frontend
            yield tool_loop_runner.build_tool_results_event(tool_results)

            # Append AI message with tool_calls and tool result messages
            tool_loop_runner.append_round_with_tool_results(
                tool_loop_state,
                round_content=round_content,
                round_tool_calls=round_tool_calls,
                tool_results=tool_results,
                round_reasoning=round_reasoning,
                round_reasoning_details=round_reasoning_details,
            )

            # Reset for next round
            round_content = ""
            round_reasoning = ""
            round_reasoning_details = None
            round_tool_calls = []

        if tool_loop_runner.should_inject_fallback_answer(tool_loop_state, full_response):
            injected = tool_loop_runner.build_fallback_answer(tool_loop_state)
            if full_response.strip():
                injected = f"\n\n{injected}"
            full_response += injected
            tool_loop_state.tool_finalize_reason = "fallback_empty_answer"
            yield injected

        yield tool_loop_runner.build_tool_diagnostics_event(tool_loop_state)

        # Yield usage data at the end
        if final_usage:
            yield {"type": "usage", "usage": final_usage}

        print(f"[OK] LLM streaming complete, total length: {len(full_response)} chars")
        if full_reasoning:
            print(f"[THINK] Reasoning content length: {len(full_reasoning)} chars")
        if final_usage:
            print(f"[USAGE] Tokens: {final_usage.prompt_tokens} in / {final_usage.completion_tokens} out")
        logger.info(f"Streaming complete: {len(full_response)} chars")

        # Log complete interaction
        from langchain_core.messages import AIMessage as AIMsg
        response_msg = AIMsg(content=full_response)

        log_extra_params = {
            "request_params": request_params,
            "call_mode": effective_call_mode.value,
            "responses_fallback_enabled": allow_responses_fallback,
        }
        if disable_thinking:
            log_extra_params["thinking_enabled"] = False
            log_extra_params["reasoning_mode"] = "none"
        elif thinking_enabled:
            log_extra_params["thinking_enabled"] = True
            if effective_reasoning_option:
                log_extra_params["reasoning_option"] = effective_reasoning_option
            if effective_reasoning_effort:
                log_extra_params["reasoning_effort"] = effective_reasoning_effort
        if full_reasoning:
            log_extra_params["reasoning_content"] = full_reasoning
        if final_usage:
            log_extra_params["usage"] = final_usage.model_dump()

        llm_logger.log_interaction(
            session_id=session_id,
            messages_sent=langchain_messages,
            response_received=response_msg,
            model=actual_model_id,
            extra_params=log_extra_params
        )
        print(f"[LOG] Streaming LLM interaction logged")

    except Exception as e:
        print(f"[ERROR] LLM streaming API call failed: {str(e)}")
        logger.error(f"Streaming API call failed: {str(e)}", exc_info=True)
        llm_logger.log_error(session_id, e, context="LLM Stream API call")
        raise


def _truncate_by_rounds(
    messages: List[Any],
    max_rounds: int,
    system_prompt: Optional[str] = None
) -> List[Any]:
    """
    Truncate message list by conversation rounds.

    Strategy: Keep system prompt and recent N rounds (1 round = 1 user message + 1 assistant reply)

    Args:
        messages: LangChain message list
        max_rounds: Maximum rounds
        system_prompt: System prompt (if any)

    Returns:
        Truncated message list
    """
    # Separate system message and conversation messages
    system_msg = None
    conversation_messages = messages

    if system_prompt and len(messages) > 0 and isinstance(messages[0], SystemMessage):
        system_msg = messages[0]
        conversation_messages = messages[1:]

    # Calculate current rounds (1 round = user + assistant)
    # Note: May have incomplete rounds (only user message without assistant reply)
    current_rounds = len(conversation_messages) // 2

    # If current rounds don't exceed limit, return directly
    if current_rounds <= max_rounds:
        return messages

    print(f"[WARN] Conversation rounds exceed limit ({current_rounds} > {max_rounds}), truncating to recent {max_rounds} rounds...")

    # Keep the most recent max_rounds rounds
    # Each round includes user + assistant, total max_rounds * 2 messages
    keep_count = max_rounds * 2
    kept_conversation = conversation_messages[-keep_count:]

    # Reassemble
    result = []
    if system_msg:
        result.append(system_msg)
    result.extend(kept_conversation)

    print(f"      Truncation complete: kept {len(kept_conversation)} messages ({len(kept_conversation) // 2} rounds)")
    return result


def _filter_messages_by_context_boundary(messages: List[Dict]) -> Tuple[List[Dict], Optional[str]]:
    """
    Filter messages to only include those after the last context boundary
    (separator or summary). If the boundary is a summary, also return its content.

    Args:
        messages: Full message list

    Returns:
        Tuple of (filtered message list, summary content or None)
    """
    last_boundary_index = -1
    boundary_is_summary = False

    # Find last separator or summary from the end
    for i in range(len(messages) - 1, -1, -1):
        role = messages[i].get("role")
        if role == "separator" or role == "summary":
            last_boundary_index = i
            boundary_is_summary = (role == "summary")
            break

    # No boundary: return all messages
    if last_boundary_index == -1:
        return messages, None

    # Extract summary content if applicable
    summary_content = None
    if boundary_is_summary:
        summary_content = messages[last_boundary_index].get("content", "")

    # Return messages after boundary (exclude boundary itself)
    return messages[last_boundary_index + 1:], summary_content
