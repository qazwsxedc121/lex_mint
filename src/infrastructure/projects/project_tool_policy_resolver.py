"""Resolve per-project tool availability for project-scoped chat and agent flows."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from langchain_core.tools import BaseTool

from src.domain.models.project_config import get_default_project_tool_enabled_map
from src.infrastructure.config.project_service import ProjectService

logger = logging.getLogger(__name__)


class ProjectToolPolicyResolver:
    """Loads project tool settings and filters request-scoped tool exposure."""

    def __init__(self, *, project_service: ProjectService | None = None):
        self.project_service = project_service or ProjectService()

    async def get_tool_enabled_map(
        self,
        *,
        context_type: str,
        project_id: str | None,
    ) -> dict[str, bool]:
        enabled_map = get_default_project_tool_enabled_map()
        if context_type != "project" or not project_id:
            return enabled_map

        try:
            project = await self.project_service.get_project(project_id)
            if project is None:
                return enabled_map

            configured_map = getattr(project.settings.tools, "tool_enabled_map", None) or {}
            for tool_name, is_enabled in configured_map.items():
                name = str(tool_name or "").strip()
                if not name:
                    continue
                enabled_map[name] = bool(is_enabled)
        except Exception as exc:
            logger.warning("Failed to load project tool policy for %s: %s", project_id, exc)

        return enabled_map

    async def get_allowed_tool_names(
        self,
        *,
        context_type: str,
        project_id: str | None,
        candidate_tool_names: Iterable[str] | None = None,
    ) -> set[str]:
        enabled_map = await self.get_tool_enabled_map(
            context_type=context_type, project_id=project_id
        )
        allowed_names = {name for name, is_enabled in enabled_map.items() if is_enabled}
        if candidate_tool_names is None:
            return allowed_names
        candidate_set = {
            str(name or "").strip() for name in candidate_tool_names if str(name or "").strip()
        }
        return allowed_names.intersection(candidate_set)

    async def filter_tools(
        self,
        *,
        tools: list[BaseTool],
        context_type: str,
        project_id: str | None,
    ) -> list[BaseTool]:
        if context_type != "project" or not project_id:
            return tools

        allowed_names = await self.get_allowed_tool_names(
            context_type=context_type,
            project_id=project_id,
            candidate_tool_names=[tool.name for tool in tools],
        )
        return [tool for tool in tools if tool.name in allowed_names]
