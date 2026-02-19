"""Policy helpers for provider stream call behavior."""

from __future__ import annotations

from typing import Any, Dict

from src.providers.types import CallMode


def should_allow_responses_fallback(call_mode: CallMode) -> bool:
    """Whether to enable responses->chat fallback for streaming."""
    return call_mode == CallMode.RESPONSES


def build_stream_kwargs(*, allow_responses_fallback: bool) -> Dict[str, Any]:
    """Build adapter.stream kwargs based on resolved stream policy."""
    if not allow_responses_fallback:
        return {}
    return {"allow_responses_fallback": True}


def select_stream_llm(
    *,
    llm: Any,
    llm_for_tools: Any,
    tools_enabled: bool,
    force_finalize_without_tools: bool,
) -> Any:
    """Select which LLM handle should be used for the current stream pass."""
    if tools_enabled and not force_finalize_without_tools:
        return llm_for_tools
    return llm
