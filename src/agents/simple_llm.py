"""Simple LLM call service - without LangGraph"""

import os
import logging
from typing import List, Dict, Any, AsyncIterator, Optional, Union
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

from src.utils.llm_logger import get_llm_logger
from src.api.services.model_config_service import ModelConfigService
from src.api.services.file_service import FileService
from src.providers.types import TokenUsage

logger = logging.getLogger(__name__)

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

    # Convert message format
    langchain_messages = []
    if system_prompt:
        langchain_messages.append(SystemMessage(content=system_prompt))
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
            model=actual_model_id,
            extra_params={"request_params": request_params}
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
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    reasoning_effort: Optional[str] = None,
    file_service: Optional[FileService] = None
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
        file_service: File service for reading image attachments (optional)

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
        thinking_enabled=thinking_enabled,
        reasoning_effort=reasoning_effort,
        **extra_params,
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

    # === Filter messages after last separator ===
    filtered_messages = _filter_messages_after_separator(messages)
    if len(filtered_messages) < len(messages):
        print(f"[CONTEXT] Filtered messages: {len(messages)} -> {len(filtered_messages)}")
        logger.info(f"Context filtered: {len(messages)} -> {len(filtered_messages)} messages")

    # Convert message format (with multimodal support if file_service provided)
    langchain_messages = []

    # Inject system prompt (if provided)
    if system_prompt:
        langchain_messages.append(SystemMessage(content=system_prompt))

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

        log_extra_params = {"request_params": request_params}
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


def _filter_messages_after_separator(messages: List[Dict]) -> List[Dict]:
    """
    Filter messages to only include those after the last separator.

    Args:
        messages: Full message list

    Returns:
        Filtered message list (excludes separator itself)
    """
    last_separator_index = -1

    # Find last separator from the end
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "separator":
            last_separator_index = i
            break

    # No separator: return all messages
    if last_separator_index == -1:
        return messages

    # Return messages after separator (exclude separator)
    return messages[last_separator_index + 1:]
