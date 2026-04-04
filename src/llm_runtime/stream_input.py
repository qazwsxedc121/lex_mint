"""Shared prompt/context preparation for streamed LLM calls."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.infrastructure.files.file_service import FileService
from src.llm_runtime.context import (
    build_context_info_event,
    build_context_plan,
    context_segment_to_system_content,
    estimate_langchain_messages_tokens,
    filter_messages_by_context_boundary,
    get_context_limit,
    trim_to_context_limit,
)
from src.llm_runtime.messages import convert_to_langchain_messages

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedStreamInput:
    """Prepared prompt context and converted LangChain messages."""

    langchain_messages: list[BaseMessage]
    context_event: dict[str, Any]


async def prepare_stream_input(
    *,
    runtime: Any,
    messages: list[dict[str, Any]],
    session_id: str,
    system_prompt: str | None,
    context_segments: dict[str, str | None] | None,
    max_rounds: int | None,
    file_service: FileService | None,
) -> PreparedStreamInput:
    """Build prompt messages and the matching context info event."""
    filtered_messages, summary_content = filter_messages_by_context_boundary(messages)
    _log_context_filtering(
        original_count=len(messages),
        filtered_count=len(filtered_messages),
        summary_content=summary_content,
    )

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

    langchain_messages = await _build_langchain_messages(
        context_plan=context_plan,
        session_id=session_id,
        file_service=file_service,
    )
    langchain_messages = trim_to_context_limit(langchain_messages, max_input_tokens)
    estimated_prompt_tokens = estimate_langchain_messages_tokens(langchain_messages)

    return PreparedStreamInput(
        langchain_messages=langchain_messages,
        context_event=build_context_info_event(
            context_plan=context_plan,
            context_budget=max_input_tokens,
            context_window=context_window,
            estimated_prompt_tokens=estimated_prompt_tokens,
        ),
    )


async def _build_langchain_messages(
    *,
    context_plan: Any,
    session_id: str,
    file_service: FileService | None,
) -> list[BaseMessage]:
    langchain_messages: list[BaseMessage] = [
        SystemMessage(content=context_segment_to_system_content(segment.name, segment.content))
        for segment in context_plan.system_segments
    ]
    langchain_messages.extend(
        await _build_chat_messages(
            chat_messages=context_plan.chat_messages,
            session_id=session_id,
            file_service=file_service,
        )
    )
    return langchain_messages


async def _build_chat_messages(
    *,
    chat_messages: list[dict[str, Any]],
    session_id: str,
    file_service: FileService | None,
) -> list[BaseMessage]:
    if file_service:
        converted_messages = await convert_to_langchain_messages(
            chat_messages,
            session_id,
            file_service,
        )
        _log_chat_messages(chat_messages, include_image_hint=True)
        return converted_messages

    simple_messages: list[BaseMessage] = []
    for msg in chat_messages:
        role = msg.get("role")
        if role == "user":
            simple_messages.append(HumanMessage(content=msg["content"]))
        elif role == "assistant":
            simple_messages.append(AIMessage(content=msg["content"]))
    _log_chat_messages(chat_messages, include_image_hint=False)
    return simple_messages


def _log_context_filtering(
    *,
    original_count: int,
    filtered_count: int,
    summary_content: str | None,
) -> None:
    if filtered_count >= original_count:
        return
    print(f"[CONTEXT] Filtered messages: {original_count} -> {filtered_count}")
    logger.info("Context filtered: %s -> %s messages", original_count, filtered_count)
    if summary_content:
        print(f"[CONTEXT] Summary context injected ({len(summary_content)} chars)")
        logger.info("Summary context injected: %s chars", len(summary_content))


def _log_chat_messages(
    chat_messages: list[dict[str, Any]],
    *,
    include_image_hint: bool,
) -> None:
    for index, msg in enumerate(chat_messages):
        role = msg.get("role", "unknown")
        content_preview = msg.get("content", "")[:50]
        if include_image_hint:
            attachments = msg.get("attachments", [])
            has_images = any(att.get("mime_type", "").startswith("image/") for att in attachments)
            suffix = " [with images]" if has_images else ""
            print(f"      Message {index + 1}: {role} - {content_preview}...{suffix}")
        elif role in {"user", "assistant"}:
            print(f"      Message {index + 1}: {role} - {content_preview}...")
