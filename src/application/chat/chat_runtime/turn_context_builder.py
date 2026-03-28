"""Context builder for one group assistant turn."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from src.application.chat.source_diagnostics import merge_source_groups

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroupTurnContext:
    """Prepared context for one assistant turn execution."""

    assistant_name: str
    model_id: str
    messages: list[dict[str, Any]]
    history_hint: str
    identity_prompt: str
    instruction_prompt: str | None
    system_prompt: str
    sources: list[dict[str, Any]]


class GroupTurnContextBuilder:
    """Builds prompts/messages for one group assistant turn."""

    def __init__(
        self,
        *,
        storage: Any,
        memory_service: Any,
        build_rag_context_and_sources: Callable[
            ..., Awaitable[tuple[str | None, list[dict[str, Any]]]]
        ],
        build_group_history_hint: Callable[[list[dict[str, Any]], str, dict[str, str]], str],
        build_group_identity_prompt: Callable[[str, str, list[str], dict[str, str]], str],
        build_group_instruction_prompt: Callable[[str | None, dict[str, Any] | None], str | None],
    ):
        self.storage = storage
        self.memory_service = memory_service
        self.build_rag_context_and_sources = build_rag_context_and_sources
        self.build_group_history_hint = build_group_history_hint
        self.build_group_identity_prompt = build_group_identity_prompt
        self.build_group_instruction_prompt = build_group_instruction_prompt

    async def build(
        self,
        *,
        session_id: str,
        assistant_id: str,
        assistant_obj: Any,
        group_assistants: list[str],
        assistant_name_map: dict[str, str],
        raw_user_message: str,
        context_type: str,
        project_id: str | None,
        search_context: str | None,
        search_sources: list[dict[str, Any]],
        instruction: str | None = None,
        committee_turn_packet: dict[str, Any] | None = None,
    ) -> GroupTurnContext:
        """Build complete turn context with system prompt stacking."""
        session = await self.storage.get_session(
            session_id, context_type=context_type, project_id=project_id
        )
        messages = session["state"]["messages"]

        assistant_name = assistant_obj.name
        model_id = assistant_obj.model_id

        history_hint = self.build_group_history_hint(
            messages,
            assistant_id,
            assistant_name_map,
        )
        identity_prompt = self.build_group_identity_prompt(
            assistant_id,
            assistant_name,
            group_assistants,
            assistant_name_map,
        )
        instruction_prompt = self.build_group_instruction_prompt(
            instruction,
            committee_turn_packet,
        )

        system_prompt = assistant_obj.system_prompt
        prompt_parts = [identity_prompt]
        if history_hint:
            prompt_parts.append(history_hint)
        if instruction_prompt:
            prompt_parts.append(instruction_prompt)
        if system_prompt:
            prompt_parts.append(system_prompt)
        system_prompt = "\n\n".join(prompt_parts)

        assistant_memory_enabled = bool(getattr(assistant_obj, "memory_enabled", True))
        memory_sources: list[dict[str, Any]] = []
        try:
            memory_context, memory_sources = self.memory_service.build_memory_context(
                query=raw_user_message,
                assistant_id=assistant_id,
                include_global=True,
                include_assistant=assistant_memory_enabled,
            )
            if memory_context:
                system_prompt = (
                    f"{system_prompt}\n\n{memory_context}" if system_prompt else memory_context
                )
        except Exception as e:
            logger.warning("[GroupChat] Memory retrieval failed for %s: %s", assistant_id, e)

        rag_context, rag_sources = await self.build_rag_context_and_sources(
            context_type=context_type,
            project_id=project_id,
            raw_user_message=raw_user_message,
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
            runtime_model_id=model_id,
        )
        if rag_context:
            system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context
        if search_context:
            system_prompt = (
                f"{system_prompt}\n\n{search_context}" if system_prompt else search_context
            )
        sources = merge_source_groups(memory_sources, search_sources, rag_sources)

        return GroupTurnContext(
            assistant_name=assistant_name,
            model_id=model_id,
            messages=messages,
            history_hint=history_hint,
            identity_prompt=identity_prompt,
            instruction_prompt=instruction_prompt,
            system_prompt=system_prompt,
            sources=sources,
        )
