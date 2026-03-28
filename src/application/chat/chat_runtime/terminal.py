"""Terminal event helpers shared across orchestration modes."""

from __future__ import annotations

from typing import Any

from .base import ChatOrchestrationCancelToken


def cancellation_reason(
    cancel_token: ChatOrchestrationCancelToken | None,
    *,
    default: str = "cancelled",
) -> str:
    """Normalize cooperative cancellation reason."""
    if cancel_token and isinstance(cancel_token.reason, str):
        cleaned_reason = cancel_token.reason.strip()
        if cleaned_reason:
            return cleaned_reason
    return default


def build_group_done_event(*, mode: str, rounds: int, reason: str) -> dict[str, Any]:
    """Build canonical group terminal event."""
    return {
        "type": "group_done",
        "mode": mode,
        "reason": reason,
        "rounds": rounds,
    }


def build_compare_complete_event(
    *,
    model_results: dict[str, dict[str, Any]],
    reason: str = "completed",
) -> dict[str, Any]:
    """Build canonical compare terminal event."""
    return {
        "type": "compare_complete",
        "model_results": model_results,
        "reason": reason,
    }
