"""Resolve effective knowledge bases for project-scoped chat and agent flows."""

from __future__ import annotations

import logging

from src.application.chat.service_contracts import AssistantLike
from src.infrastructure.config.project_service import ProjectService
from src.infrastructure.knowledge.knowledge_base_service import KnowledgeBaseService

logger = logging.getLogger(__name__)


class ProjectKnowledgeBaseResolver:
    """Combines assistant and project knowledge-base bindings into one effective list."""

    def __init__(
        self,
        *,
        project_service: ProjectService | None = None,
        knowledge_base_service: KnowledgeBaseService | None = None,
    ):
        self.project_service = project_service or ProjectService()
        self.knowledge_base_service = knowledge_base_service or KnowledgeBaseService()

    async def resolve_effective_kb_ids(
        self,
        *,
        assistant_id: str | None,
        assistant_obj: AssistantLike | None,
        context_type: str,
        project_id: str | None,
    ) -> list[str]:
        assistant_for_resolution = assistant_obj
        if assistant_for_resolution is None and assistant_id:
            try:
                from src.infrastructure.config.assistant_config_service import (
                    AssistantConfigService,
                )

                assistant_for_resolution = await AssistantConfigService().get_assistant(
                    assistant_id
                )
            except Exception as exc:
                logger.warning(
                    "Failed to load assistant '%s' during KB resolution: %s", assistant_id, exc
                )

        assistant_kb_ids: list[str] = []
        if assistant_id and assistant_for_resolution is not None:
            assistant_kb_ids = list(
                getattr(assistant_for_resolution, "knowledge_base_ids", None) or []
            )

        project_kb_ids: list[str] = []
        knowledge_base_mode = "append"
        if context_type == "project" and project_id:
            try:
                project = await self.project_service.get_project(project_id)
                if project is not None:
                    rag_settings = project.settings.rag
                    project_kb_ids = list(getattr(rag_settings, "knowledge_base_ids", None) or [])
                    knowledge_base_mode = str(
                        getattr(rag_settings, "knowledge_base_mode", "append") or "append"
                    )
            except Exception as exc:
                logger.warning("Failed to load project settings for KB resolution: %s", exc)

        if knowledge_base_mode == "override" and project_kb_ids:
            raw_ids = project_kb_ids
        else:
            raw_ids = [*assistant_kb_ids, *project_kb_ids]

        normalized_ids: list[str] = []
        seen = set()
        for kb_id in raw_ids:
            normalized = str(kb_id or "").strip()
            if not normalized or normalized in seen:
                continue
            normalized_ids.append(normalized)
            seen.add(normalized)

        if not normalized_ids:
            return []

        enabled_ids: list[str] = []
        for kb_id in normalized_ids:
            try:
                kb = await self.knowledge_base_service.get_knowledge_base(kb_id)
            except Exception as exc:
                logger.warning("Failed to inspect knowledge base '%s': %s", kb_id, exc)
                continue

            if kb is None or not getattr(kb, "enabled", False):
                continue
            enabled_ids.append(kb_id)

        return enabled_ids
