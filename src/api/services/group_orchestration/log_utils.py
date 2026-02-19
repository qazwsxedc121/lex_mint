"""Shared log/text helpers for group orchestration."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def truncate_log_text(text: Optional[str], max_chars: int = 1600) -> str:
    """Trim text for debug logs while preserving head and tail context."""
    content = (text or "").replace("\r", "")
    if len(content) <= max_chars:
        return content
    head = int(max_chars * 0.7)
    tail = max_chars - head
    return f"{content[:head]}\n...[truncated]...\n{content[-tail:]}"


def build_messages_preview_for_log(
    messages: List[Dict[str, Any]],
    *,
    max_messages: int = 10,
    max_chars: int = 220,
) -> List[Dict[str, Any]]:
    """Build a compact recent message view for group context debugging."""
    preview: List[Dict[str, Any]] = []
    for msg in messages[-max_messages:]:
        preview.append(
            {
                "role": msg.get("role"),
                "assistant_id": msg.get("assistant_id"),
                "message_id": msg.get("message_id"),
                "content": truncate_log_text(msg.get("content") or "", max_chars),
            }
        )
    return preview
