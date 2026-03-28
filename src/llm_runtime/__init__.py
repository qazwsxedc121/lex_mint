"""LLM runtime package with explicit responsibility boundaries."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from src.infrastructure.config.model_config_service import ModelConfigService
from src.infrastructure.files.file_service import FileService
from src.utils.llm_logger import get_llm_logger

from .context import (
    build_context_info_event,
    build_context_plan,
    calculate_output_reserve,
    context_segment_to_system_content,
    estimate_langchain_messages_tokens,
    estimate_total_tokens,
    filter_messages_by_context_boundary,
    get_context_limit,
    trim_to_context_limit,
    truncate_by_rounds,
)
from .messages import convert_to_langchain_messages
from .reasoning import (
    ReasoningDecision,
    build_reasoning_decision_payload,
    log_reasoning_decision,
    resolve_reasoning_decision,
)
from .streaming_client import call_llm_stream as _call_llm_stream_impl
from .sync_client import call_llm as _call_llm_impl
from .think_tag_filter import ThinkTagStreamFilter, strip_think_blocks


def call_llm(
    messages: list[dict[str, str]],
    session_id: str = "unknown",
    model_id: str | None = None,
    system_prompt: str | None = None,
    context_segments: dict[str, str | None] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
) -> str:
    """Stable runtime entrypoint with injectable factories for tests."""
    return _call_llm_impl(
        messages=messages,
        session_id=session_id,
        model_id=model_id,
        system_prompt=system_prompt,
        context_segments=context_segments,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        top_k=top_k,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        model_service_factory=ModelConfigService,
        llm_logger_factory=get_llm_logger,
    )


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
    tool_executor: Any | None = None,
) -> AsyncIterator[str | dict[str, Any]]:
    """Stable streaming runtime entrypoint with injectable factories for tests."""
    async for chunk in _call_llm_stream_impl(
        messages=messages,
        session_id=session_id,
        model_id=model_id,
        system_prompt=system_prompt,
        context_segments=context_segments,
        max_rounds=max_rounds,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        top_k=top_k,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        reasoning_effort=reasoning_effort,
        file_service=file_service,
        tools=tools,
        tool_executor=tool_executor,
        model_service_factory=ModelConfigService,
        llm_logger_factory=get_llm_logger,
    ):
        yield chunk


_build_context_plan = build_context_plan
_build_reasoning_decision_payload = build_reasoning_decision_payload
_calculate_output_reserve = calculate_output_reserve
_context_segment_to_system_content = context_segment_to_system_content
_estimate_langchain_messages_tokens = estimate_langchain_messages_tokens
_estimate_total_tokens = estimate_total_tokens
_filter_messages_by_context_boundary = filter_messages_by_context_boundary
_get_context_limit = get_context_limit
_trim_to_context_limit = trim_to_context_limit
_truncate_by_rounds = truncate_by_rounds

__all__ = [
    "ReasoningDecision",
    "build_context_info_event",
    "build_context_plan",
    "build_reasoning_decision_payload",
    "calculate_output_reserve",
    "call_llm",
    "call_llm_stream",
    "context_segment_to_system_content",
    "convert_to_langchain_messages",
    "estimate_langchain_messages_tokens",
    "estimate_total_tokens",
    "filter_messages_by_context_boundary",
    "get_context_limit",
    "log_reasoning_decision",
    "resolve_reasoning_decision",
    "ThinkTagStreamFilter",
    "strip_think_blocks",
    "trim_to_context_limit",
    "truncate_by_rounds",
    "_build_context_plan",
    "_build_reasoning_decision_payload",
    "_calculate_output_reserve",
    "_context_segment_to_system_content",
    "_estimate_langchain_messages_tokens",
    "_estimate_total_tokens",
    "_filter_messages_by_context_boundary",
    "_get_context_limit",
    "_trim_to_context_limit",
    "_truncate_by_rounds",
]
