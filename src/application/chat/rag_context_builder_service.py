"""Build assistant/project RAG context for chat flows."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.application.chat.service_contracts import AssistantLike

logger = logging.getLogger(__name__)


class RagContextBuilderService:
    """Resolve effective KBs and retrieve prompt-ready RAG context."""

    async def build_context_and_sources(
        self,
        *,
        raw_user_message: str,
        assistant_id: Optional[str],
        assistant_obj: Optional[AssistantLike] = None,
        runtime_model_id: Optional[str] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        rag_sources: List[Dict[str, Any]] = []

        try:
            assistant_for_rag = assistant_obj
            if assistant_for_rag is None and assistant_id:
                from src.infrastructure.config.assistant_config_service import AssistantConfigService

                assistant_service = AssistantConfigService()
                assistant_for_rag = await assistant_service.get_assistant(assistant_id)

            from src.infrastructure.projects.project_knowledge_base_resolver import ProjectKnowledgeBaseResolver

            kb_ids = await ProjectKnowledgeBaseResolver().resolve_effective_kb_ids(
                assistant_id=assistant_id,
                assistant_obj=assistant_for_rag,
                context_type=context_type,
                project_id=project_id,
            )
            if not kb_ids:
                return None, rag_sources

            from src.infrastructure.retrieval.rag_service import RagService

            rag_service = RagService()
            rag_results, rag_diagnostics = await rag_service.retrieve_with_diagnostics(
                raw_user_message,
                kb_ids,
                runtime_model_id=runtime_model_id,
            )
            rag_sources.append(rag_service.build_rag_diagnostics_source(rag_diagnostics))
            if not rag_results:
                return None, rag_sources

            rag_context = rag_service.build_rag_context(raw_user_message, rag_results)
            rag_sources.extend([result.to_dict() for result in rag_results])
            return rag_context, rag_sources
        except Exception as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            return None, rag_sources
