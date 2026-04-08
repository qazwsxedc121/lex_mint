"""Shared context assembly for single and compare chat flows."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from src.application.chat.service_contracts import (
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
from src.application.chat.source_diagnostics import merge_source_groups
from src.tools.registry import get_tool_registry

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
        rag_context_builder: Callable[..., Awaitable[tuple[str | None, list[SourcePayload]]]],
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
        project_id: str | None = None,
        use_web_search: bool = False,
        search_query: str | None = None,
    ) -> ContextPayload:
        """Prepare context payload consumed by orchestrators."""
        web_tools_loaded = bool(get_tool_registry().is_plugin_loaded("web_tools"))
        session = await self.storage.get_session(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )
        messages = session["state"]["messages"]
        assistant_id = session.get("assistant_id")
        model_id = session.get("model_id")

        base_system_prompt = None
        max_rounds = None
        assistant_params: dict[str, Any] = {}
        assistant_obj: AssistantLike | None = None
        memory_context: str | None = None
        webpage_context: str | None = None
        search_context: str | None = None
        rag_context: str | None = None
        structured_source_context: str | None = None

        if assistant_id:
            from src.infrastructure.config.assistant_config_service import AssistantConfigService

            assistant_service = AssistantConfigService()
            try:
                assistant = await assistant_service.require_enabled_assistant(assistant_id)
                assistant_obj = assistant
                base_system_prompt = assistant.system_prompt
                max_rounds = assistant.max_rounds
                assistant_params = self._assistant_params_from_assistant(assistant)
            except ValueError:
                raise
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

        assistant_memory_enabled = bool(getattr(assistant_obj, "memory_enabled", True))
        resolved_model_id = str(model_id or "")

        memory_sources: list[SourcePayload] = []
        try:
            include_assistant_memory = bool(assistant_id and assistant_memory_enabled)
            memory_context, memory_sources = self.memory_service.build_memory_context(
                query=raw_user_message,
                assistant_id=assistant_id if include_assistant_memory else None,
                include_global=True,
                include_assistant=include_assistant_memory,
            )
        except Exception as e:
            logger.warning("Memory retrieval failed: %s", e)

        webpage_sources: list[SourcePayload] = []
        if web_tools_loaded:
            try:
                webpage_context, webpage_source_models = await self.webpage_service.build_context(
                    raw_user_message
                )
                if webpage_source_models:
                    webpage_sources = [s.model_dump() for s in webpage_source_models]
            except Exception as e:
                logger.warning("Webpage parsing failed: %s", e)

        search_sources: list[SourcePayload] = []
        if use_web_search and web_tools_loaded:
            query = (search_query or raw_user_message).strip()
            if len(query) > 200:
                query = query[:200]
            try:
                sources = await self.search_service.search(query)
                search_sources = [s.model_dump() for s in sources]
                if sources:
                    search_context = self.search_service.build_search_context(query, sources)
            except Exception as e:
                logger.warning("Web search failed: %s", e)

        rag_context, rag_sources = await self.rag_context_builder(
            raw_user_message=raw_user_message,
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
            runtime_model_id=resolved_model_id,
            context_type=context_type,
            project_id=project_id,
        )

        all_sources = merge_source_groups(
            memory_sources,
            webpage_sources,
            search_sources,
            rag_sources,
        )
        structured_source_context = self._build_structured_source_context(
            raw_user_message=raw_user_message,
            all_sources=all_sources,
        )
        system_prompt = self._compose_system_prompt(
            base_system_prompt,
            memory_context,
            webpage_context,
            search_context,
            rag_context,
            structured_source_context,
        )

        return ContextPayload(
            messages=messages,
            system_prompt=system_prompt,
            assistant_params=assistant_params,
            all_sources=all_sources,
            model_id=resolved_model_id,
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
            assistant_memory_enabled=assistant_memory_enabled,
            max_rounds=max_rounds,
            base_system_prompt=base_system_prompt,
            memory_context=memory_context,
            webpage_context=webpage_context,
            search_context=search_context,
            rag_context=rag_context,
            structured_source_context=structured_source_context,
        )

    @staticmethod
    def _assistant_params_from_assistant(assistant: AssistantLike) -> dict[str, Any]:
        return {
            "temperature": assistant.temperature,
            "max_tokens": assistant.max_tokens,
            "top_p": assistant.top_p,
            "top_k": assistant.top_k,
            "frequency_penalty": assistant.frequency_penalty,
            "presence_penalty": assistant.presence_penalty,
        }

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

    @staticmethod
    def _compose_system_prompt(*segments: str | None) -> str | None:
        parts = [
            str(segment).strip()
            for segment in segments
            if isinstance(segment, str) and segment.strip()
        ]
        return "\n\n".join(parts) if parts else None

    def _build_structured_source_context(
        self,
        *,
        raw_user_message: str,
        all_sources: list[SourcePayload],
    ) -> str | None:
        if not all_sources or not self._is_structured_source_context_enabled():
            return None
        try:
            source_tags = self.source_context_service.build_source_tags(
                raw_user_message, all_sources
            )
            if not source_tags:
                return None
            structured_context = self.source_context_service.apply_template(
                raw_user_message, source_tags
            )
            if not structured_context:
                return None
            logger.info(
                "[SOURCE_CONTEXT] structured source context injected: source_count=%d",
                len(all_sources),
            )
            return structured_context
        except Exception as e:
            logger.warning("Structured source context injection failed: %s", e)
            return None
