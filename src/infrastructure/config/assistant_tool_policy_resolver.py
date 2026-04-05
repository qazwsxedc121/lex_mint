"""Resolve assistant-scoped tool availability for chat flows."""

from __future__ import annotations

from collections.abc import Iterable

from src.application.chat.service_contracts import AssistantLike
from src.domain.models.assistant_config import get_default_assistant_tool_enabled_map

NON_CONFIGURABLE_ASSISTANT_TOOLS = {"search_knowledge", "read_knowledge"}


class AssistantToolPolicyResolver:
    """Build an effective assistant-level tool allow-list for one request."""

    async def get_tool_enabled_map(
        self,
        *,
        assistant_id: str | None,
        assistant_obj: AssistantLike | None,
    ) -> dict[str, bool]:
        _ = assistant_id
        enabled_map = get_default_assistant_tool_enabled_map()
        configured_map = getattr(assistant_obj, "tool_enabled_map", None) or {}
        if not isinstance(configured_map, dict):
            return enabled_map
        for tool_name, is_enabled in configured_map.items():
            name = str(tool_name or "").strip()
            if not name:
                continue
            # Knowledge tools are controlled by knowledge-base availability, not assistant toggles.
            if name in NON_CONFIGURABLE_ASSISTANT_TOOLS:
                continue
            enabled_map[name] = bool(is_enabled)
        return enabled_map

    async def get_allowed_tool_names(
        self,
        *,
        assistant_id: str | None,
        assistant_obj: AssistantLike | None,
        candidate_tool_names: Iterable[str] | None = None,
    ) -> set[str]:
        enabled_map = await self.get_tool_enabled_map(
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
        )
        allowed_names = {name for name, is_enabled in enabled_map.items() if is_enabled}
        if candidate_tool_names is None:
            return allowed_names
        candidate_set = {
            str(name or "").strip() for name in candidate_tool_names if str(name or "").strip()
        }
        return allowed_names.intersection(candidate_set)
