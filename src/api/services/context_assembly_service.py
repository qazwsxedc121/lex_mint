"""Shared context assembly for single and compare chat flows."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .service_contracts import (
    AssistantLike,
    ContextPayload,
    MemoryContextServiceLike,
    RagConfigServiceLike,
    SearchServiceLike,
    SessionStorageLike,
    SourceContextServiceLike,
    SourcePayload,
    WebpageServiceLike,
)

logger = logging.getLogger(__name__)


class ContextAssemblyService:
    """Builds runtime LLM context from session, retrieval, and optional search."""

    def __init__(
        self,
        *,
        storage: SessionStorageLike,
        memory_service: MemoryContextServiceLike,
        webpage_service: WebpageServiceLike,
        search_service: SearchServiceLike,
        source_context_service: SourceContextServiceLike,
        rag_config_service: RagConfigServiceLike,
        rag_context_builder: Callable[..., Awaitable[tuple[Optional[str], List[SourcePayload]]]],
    ):
        self.storage = storage
        self.memory_service = memory_service
        self.webpage_service = webpage_service
        self.search_service = search_service
        self.source_context_service = source_context_service
        self.rag_config_service = rag_config_service
        self.rag_context_builder = rag_context_builder

    async def prepare_context(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
    ) -> ContextPayload:
        """Prepare context payload consumed by orchestrators."""
        session = await self.storage.get_session(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )
        messages = session["state"]["messages"]
        assistant_id = session.get("assistant_id")
        model_id = session.get("model_id")

        system_prompt = None
        max_rounds = None
        assistant_params: Dict[str, Any] = {}
        assistant_obj: Optional[AssistantLike] = None

        if assistant_id and not assistant_id.startswith("__legacy_model_"):
            from .assistant_config_service import AssistantConfigService

            assistant_service = AssistantConfigService()
            try:
                assistant = await assistant_service.get_assistant(assistant_id)
                if assistant:
                    assistant_obj = assistant
                    system_prompt = assistant.system_prompt
                    max_rounds = assistant.max_rounds
                    assistant_params = self._assistant_params_from_assistant(assistant)
            except Exception as e:
                logger.warning("Failed to load assistant config: %s, using defaults", e)

        param_overrides = session.get("param_overrides", {})
        if param_overrides:
            if "model_id" in param_overrides:
                model_id = param_overrides["model_id"]
            if "max_rounds" in param_overrides:
                max_rounds = param_overrides["max_rounds"]
            for key in [
                "temperature",
                "max_tokens",
                "top_p",
                "top_k",
                "frequency_penalty",
                "presence_penalty",
            ]:
                if key in param_overrides:
                    assistant_params[key] = param_overrides[key]

        is_legacy_assistant = bool(assistant_id and assistant_id.startswith("__legacy_model_"))
        assistant_memory_enabled = bool(getattr(assistant_obj, "memory_enabled", True))
        resolved_model_id = str(model_id or "")

        memory_sources: List[SourcePayload] = []
        try:
            include_assistant_memory = bool(
                assistant_id and not is_legacy_assistant and assistant_memory_enabled
            )
            memory_context, memory_sources = self.memory_service.build_memory_context(
                query=raw_user_message,
                assistant_id=assistant_id if include_assistant_memory else None,
                include_global=True,
                include_assistant=include_assistant_memory,
            )
            if memory_context:
                system_prompt = f"{system_prompt}\n\n{memory_context}" if system_prompt else memory_context
        except Exception as e:
            logger.warning("Memory retrieval failed: %s", e)

        webpage_sources: List[SourcePayload] = []
        try:
            webpage_context, webpage_source_models = await self.webpage_service.build_context(raw_user_message)
            if webpage_source_models:
                webpage_sources = [s.model_dump() for s in webpage_source_models]
            if webpage_context:
                system_prompt = f"{system_prompt}\n\n{webpage_context}" if system_prompt else webpage_context
        except Exception as e:
            logger.warning("Webpage parsing failed: %s", e)

        search_sources: List[SourcePayload] = []
        if use_web_search:
            query = (search_query or raw_user_message).strip()
            if len(query) > 200:
                query = query[:200]
            try:
                sources = await self.search_service.search(query)
                search_sources = [s.model_dump() for s in sources]
                if sources:
                    search_context = self.search_service.build_search_context(query, sources)
                    if search_context:
                        system_prompt = (
                            f"{system_prompt}\n\n{search_context}" if system_prompt else search_context
                        )
            except Exception as e:
                logger.warning("Web search failed: %s", e)

        rag_context, rag_sources = await self.rag_context_builder(
            raw_user_message=raw_user_message,
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
            runtime_model_id=resolved_model_id,
        )
        if rag_context:
            system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context

        all_sources = self._merge_all_sources(
            memory_sources,
            webpage_sources,
            search_sources,
            rag_sources,
        )
        system_prompt = self._append_structured_source_context(
            raw_user_message=raw_user_message,
            system_prompt=system_prompt,
            all_sources=all_sources,
        )

        return ContextPayload(
            messages=messages,
            system_prompt=system_prompt,
            assistant_params=assistant_params,
            all_sources=all_sources,
            model_id=resolved_model_id,
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
            is_legacy_assistant=is_legacy_assistant,
            assistant_memory_enabled=assistant_memory_enabled,
            max_rounds=max_rounds,
        )

    @staticmethod
    def _assistant_params_from_assistant(assistant: AssistantLike) -> Dict[str, Any]:
        return {
            "temperature": assistant.temperature,
            "max_tokens": assistant.max_tokens,
            "top_p": assistant.top_p,
            "top_k": assistant.top_k,
            "frequency_penalty": assistant.frequency_penalty,
            "presence_penalty": assistant.presence_penalty,
        }

    @staticmethod
    def _merge_all_sources(*source_groups: List[SourcePayload]) -> List[SourcePayload]:
        merged: List[SourcePayload] = []
        for group in source_groups:
            if group:
                merged.extend(group)
        return merged

    def _is_structured_source_context_enabled(self) -> bool:
        try:
            self.rag_config_service.reload_config()
            return bool(
                getattr(
                    self.rag_config_service.config.retrieval,
                    "structured_source_context_enabled",
                    False,
                )
            )
        except Exception as e:
            logger.warning("Failed to read structured source context setting: %s", e)
            return False

    def _append_structured_source_context(
        self,
        *,
        raw_user_message: str,
        system_prompt: Optional[str],
        all_sources: List[SourcePayload],
    ) -> Optional[str]:
        if not all_sources or not self._is_structured_source_context_enabled():
            return system_prompt
        try:
            source_tags = self.source_context_service.build_source_tags(raw_user_message, all_sources)
            if not source_tags:
                return system_prompt
            structured_context = self.source_context_service.apply_template(raw_user_message, source_tags)
            if not structured_context:
                return system_prompt
            logger.info(
                "[SOURCE_CONTEXT] structured source context injected: source_count=%d",
                len(all_sources),
            )
            return f"{system_prompt}\n\n{structured_context}" if system_prompt else structured_context
        except Exception as e:
            logger.warning("Structured source context injection failed: %s", e)
            return system_prompt
