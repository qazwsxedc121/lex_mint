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
    SessionStorageLike,
    SourceContextServiceLike,
    SourcePayload,
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
        source_context_service: SourceContextServiceLike,
        rag_config_service: RagConfigServiceLike,
        rag_context_builder: Callable[..., Awaitable[tuple[str | None, list[SourcePayload]]]],
    ):
        self.storage = storage
        self.memory_service = memory_service
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
        context_capabilities: list[str] | None = None,
        context_capability_args: dict[str, dict[str, Any]] | None = None,
    ) -> ContextPayload:
        """Prepare context payload consumed by orchestrators."""
        tool_registry = get_tool_registry()
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
        capability_contexts: dict[str, str] = {}
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

        normalized_capabilities = self._normalize_context_capabilities(context_capabilities)
        normalized_capability_args = self._normalize_context_capability_args(
            context_capability_args
        )
        unknown_args = sorted(set(normalized_capability_args.keys()) - set(normalized_capabilities))
        if unknown_args:
            raise ValueError(
                "context_capability_args contains ids that are not requested: "
                + ", ".join(unknown_args)
            )

        capability_sources: list[SourcePayload] = []
        for capability_id in normalized_capabilities:
            if not tool_registry.has_chat_capability(capability_id):
                raise ValueError(f"Unknown or unavailable context capability: {capability_id}")
            handler = tool_registry.get_context_capability_handler(capability_id)
            if handler is None:
                raise ValueError(f"Context capability is not executable: {capability_id}")
            try:
                payload = await tool_registry.execute_context_capability_async(
                    capability_id,
                    raw_user_message=raw_user_message,
                    args=normalized_capability_args.get(capability_id) or {},
                    context_type=context_type,
                    project_id=project_id,
                    session_id=session_id,
                )
                context_text = payload.get("context")
                context_key = str(payload.get("context_key") or capability_id).strip()
                if isinstance(context_text, str) and context_text.strip():
                    capability_contexts[context_key] = context_text.strip()
                raw_sources = payload.get("sources")
                if isinstance(raw_sources, list):
                    for item in raw_sources:
                        if isinstance(item, dict):
                            capability_sources.append(item)
            except ValueError:
                raise
            except Exception as e:
                logger.warning("Context capability failed (%s): %s", capability_id, e)

        webpage_context = capability_contexts.get("webpage_context")
        search_context = capability_contexts.get("search_context")

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
            capability_sources,
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
            capability_contexts=capability_contexts,
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

    @staticmethod
    def _normalize_context_capabilities(capabilities: list[str] | None) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in capabilities or []:
            capability_id = str(raw or "").strip()
            if not capability_id or capability_id in seen:
                continue
            seen.add(capability_id)
            normalized.append(capability_id)
        return normalized

    @staticmethod
    def _normalize_context_capability_args(
        capability_args: dict[str, dict[str, Any]] | None,
    ) -> dict[str, dict[str, Any]]:
        if capability_args is None:
            return {}
        if not isinstance(capability_args, dict):
            raise ValueError("context_capability_args must be an object")
        normalized: dict[str, dict[str, Any]] = {}
        for raw_key, raw_value in capability_args.items():
            capability_id = str(raw_key or "").strip()
            if not capability_id:
                continue
            if raw_value is None:
                normalized[capability_id] = {}
                continue
            if not isinstance(raw_value, dict):
                raise ValueError(f"context_capability_args['{capability_id}'] must be an object")
            normalized[capability_id] = dict(raw_value)
        return normalized

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
