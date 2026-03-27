"""Synchronous LLM runtime entry point."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.infrastructure.config.model_config_service import ModelConfigService
from src.utils.llm_logger import get_llm_logger

from .context import (
    build_context_plan,
    context_segment_to_system_content,
    filter_messages_by_context_boundary,
    get_context_limit,
    trim_to_context_limit,
)
from .params import build_llm_request_params

logger = logging.getLogger(__name__)

ModelServiceFactory = Callable[[], ModelConfigService]
LoggerFactory = Callable[[], Any]


def call_llm(
    messages: List[Dict[str, str]],
    session_id: str = "unknown",
    model_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
    context_segments: Optional[Dict[str, Optional[str]]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    model_service_factory: ModelServiceFactory = ModelConfigService,
    llm_logger_factory: LoggerFactory = get_llm_logger,
) -> str:
    """Direct non-streaming LLM call."""
    llm_logger = llm_logger_factory()

    model_service = model_service_factory()
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

    actual_model_id = model_id or model_service.get_llm_instance().model_name
    request_params = build_llm_request_params(
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        top_k=top_k,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
    )

    print(f"[LLM] Preparing to call LLM (model: {actual_model_id})")
    print(f"      History messages: {len(messages)}")
    logger.info("Preparing to call LLM (model: %s), messages: %s", actual_model_id, len(messages))

    filtered_messages, summary_content = filter_messages_by_context_boundary(messages)
    if len(filtered_messages) < len(messages):
        print(f"[CONTEXT] Filtered messages: {len(messages)} -> {len(filtered_messages)}")
        logger.info("Context filtered: %s -> %s messages", len(messages), len(filtered_messages))

    max_input_tokens, _ = get_context_limit(llm=llm, capabilities=capabilities)
    context_plan = build_context_plan(
        messages=filtered_messages,
        system_prompt=system_prompt,
        context_segments=context_segments,
        summary_content=summary_content,
        max_rounds=None,
        context_budget_tokens=max_input_tokens,
    )

    langchain_messages: List[BaseMessage] = [
        SystemMessage(content=context_segment_to_system_content(segment.name, segment.content))
        for segment in context_plan.system_segments
    ]
    for index, msg in enumerate(context_plan.chat_messages):
        if msg.get("role") == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
            print(f"      Message {index + 1}: user - {msg['content'][:50]}...")
        elif msg.get("role") == "assistant":
            langchain_messages.append(AIMessage(content=msg["content"]))
            print(f"      Message {index + 1}: assistant - {msg['content'][:50]}...")

    langchain_messages = trim_to_context_limit(langchain_messages, max_input_tokens)

    try:
        print(f"[LLM] Sending {len(langchain_messages)} messages to LLM API...")
        logger.info("Calling LLM API...")

        response = llm.invoke(langchain_messages)
        response_content_raw = response.content
        response_content = (
            response_content_raw
            if isinstance(response_content_raw, str)
            else str(response_content_raw or "")
        )
        print(f"[OK] Received LLM response, length: {len(response_content)} chars")
        logger.info("Received response: %s chars", len(response_content))

        llm_logger.log_interaction(
            session_id=session_id,
            messages_sent=langchain_messages,
            response_received=response,
            model=actual_model_id,
            extra_params={"request_params": request_params},
        )
        print("[LOG] LLM interaction logged")
        return response_content
    except Exception as exc:
        print(f"[ERROR] LLM API call failed: {str(exc)}")
        logger.error("API call failed: %s", str(exc), exc_info=True)
        llm_logger.log_error(session_id, exc, context="LLM API call")
        raise
