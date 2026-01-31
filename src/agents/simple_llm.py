"""Simple LLM call service - without LangGraph"""

import os
import logging
from typing import List, Dict, Any, AsyncIterator, Optional, Union
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.utils.llm_logger import get_llm_logger
from src.api.services.model_config_service import ModelConfigService
from src.providers.types import TokenUsage

logger = logging.getLogger(__name__)


def call_llm(
    messages: List[Dict[str, str]],
    session_id: str = "unknown",
    model_id: Optional[str] = None
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
    llm = model_service.get_llm_instance(model_id)

    # Get actual model ID
    actual_model_id = model_id or model_service.get_llm_instance().model_name

    print(f"[LLM] Preparing to call LLM (model: {actual_model_id})")
    print(f"      History messages: {len(messages)}")
    logger.info(f"Preparing to call LLM (model: {actual_model_id}), messages: {len(messages)}")

    # Convert message format
    langchain_messages = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
            print(f"      Message {i+1}: user - {msg['content'][:50]}...")
        elif msg.get("role") == "assistant":
            langchain_messages.append(AIMessage(content=msg["content"]))
            print(f"      Message {i+1}: assistant - {msg['content'][:50]}...")

    try:
        print(f"[LLM] Sending {len(langchain_messages)} messages to LLM API...")
        logger.info(f"Calling LLM API...")

        # Call LLM (only once!)
        response = llm.invoke(langchain_messages)

        print(f"[OK] Received LLM response, length: {len(response.content)} chars")
        logger.info(f"Received response: {len(response.content)} chars")

        # Log interaction
        llm_logger.log_interaction(
            session_id=session_id,
            messages_sent=langchain_messages,
            response_received=response,
            model=actual_model_id
        )
        print(f"[LOG] LLM interaction logged")

        return response.content

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
    reasoning_effort: Optional[str] = None
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
        reasoning_effort: Reasoning effort level: "low", "medium", "high"

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

    # Determine if thinking should be enabled
    thinking_enabled = False
    if reasoning_effort and capabilities.reasoning:
        thinking_enabled = True
        logger.info(f"Thinking mode enabled for {model_config.id} (effort: {reasoning_effort})")
    elif reasoning_effort and not capabilities.reasoning:
        logger.warning(f"Model {model_config.id} does not support reasoning mode, ignoring reasoning_effort")

    # Get API key
    api_key = model_service.get_api_key_sync(provider_config.id)
    if not api_key:
        api_key = os.getenv(provider_config.api_key_env or "")

    if not api_key:
        raise RuntimeError(
            f"API key not found for provider '{provider_config.id}'. "
            f"Please set it via the UI or environment variable: {provider_config.api_key_env}"
        )

    # Create LLM instance via adapter
    llm = adapter.create_llm(
        model=model_config.id,
        base_url=provider_config.base_url,
        api_key=api_key,
        temperature=model_config.temperature,
        streaming=True,
        thinking_enabled=thinking_enabled,
        reasoning_effort=reasoning_effort,
    )

    actual_model_id = f"{provider_config.id}:{model_config.id}"

    print(f"[LLM] Preparing streaming call (model: {actual_model_id})")
    print(f"      History messages: {len(messages)}")
    if system_prompt:
        print(f"      Using system prompt: {system_prompt[:50]}...")
    if max_rounds:
        if max_rounds == -1:
            print(f"      Round limit: unlimited")
        else:
            print(f"      Max rounds: {max_rounds}")
    if thinking_enabled:
        print(f"      Thinking mode: enabled (effort: {reasoning_effort})")
    logger.info(f"Preparing streaming LLM call (model: {actual_model_id}), messages: {len(messages)}")

    # Convert message format
    langchain_messages = []

    # Inject system prompt (if provided)
    if system_prompt:
        langchain_messages.append(SystemMessage(content=system_prompt))

    for i, msg in enumerate(messages):
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

    try:
        print(f"[LLM] Streaming {len(langchain_messages)} messages to LLM API...")
        logger.info(f"Streaming LLM API call...")

        # Collect full response for logging
        full_response = ""
        full_reasoning = ""
        in_thinking_phase = False
        thinking_ended = False
        final_usage: Optional[TokenUsage] = None

        # Stream via adapter (unified interface)
        async for chunk in adapter.stream(llm, langchain_messages):
            # Handle thinking/reasoning content
            if chunk.thinking:
                full_reasoning += chunk.thinking
                if not in_thinking_phase:
                    in_thinking_phase = True
                    yield "<think>"
                yield chunk.thinking

            # Handle regular content
            if chunk.content:
                if in_thinking_phase and not thinking_ended:
                    thinking_ended = True
                    yield "</think>"
                full_response += chunk.content
                yield chunk.content

            # Capture usage data (usually in final chunk)
            if chunk.usage:
                final_usage = chunk.usage

        # Close thinking tag if opened but no content followed
        if in_thinking_phase and not thinking_ended:
            yield "</think>"

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

        log_extra_params = {}
        if thinking_enabled:
            log_extra_params["thinking_enabled"] = True
            log_extra_params["reasoning_effort"] = reasoning_effort
        if full_reasoning:
            log_extra_params["reasoning_content"] = full_reasoning
        if final_usage:
            log_extra_params["usage"] = final_usage.model_dump()

        llm_logger.log_interaction(
            session_id=session_id,
            messages_sent=langchain_messages,
            response_received=response_msg,
            model=actual_model_id,
            extra_params=log_extra_params if log_extra_params else None
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
