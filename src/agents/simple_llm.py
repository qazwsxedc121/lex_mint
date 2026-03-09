"""Compatibility shim for legacy `src.agents.simple_llm` imports."""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional, Union

from src.api.services.file_service import FileService
from src.api.services.model_config_service import ModelConfigService
from src.utils.llm_logger import get_llm_logger

from .llm_runtime import (
    _build_context_plan,
    _build_reasoning_decision_payload,
    _estimate_total_tokens,
    _filter_messages_by_context_boundary,
    _get_context_limit,
    _truncate_by_rounds,
    call_llm as _call_llm_impl,
    call_llm_stream as _call_llm_stream_impl,
    convert_to_langchain_messages,
)


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
) -> str:
    """Backward-compatible wrapper around `src.agents.llm_runtime.call_llm`."""
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
    tool_executor: Optional[Any] = None,
) -> AsyncIterator[Union[str, Dict[str, Any]]]:
    """Backward-compatible wrapper around `src.agents.llm_runtime.call_llm_stream`."""
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


__all__ = [
    "ModelConfigService",
    "call_llm",
    "call_llm_stream",
    "convert_to_langchain_messages",
    "get_llm_logger",
    "_build_context_plan",
    "_build_reasoning_decision_payload",
    "_estimate_total_tokens",
    "_filter_messages_by_context_boundary",
    "_get_context_limit",
    "_truncate_by_rounds",
]
