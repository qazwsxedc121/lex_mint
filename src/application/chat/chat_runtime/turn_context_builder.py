"""Context builder for one group assistant turn."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroupTurnContext:
    """Prepared context for one assistant turn execution."""

    assistant_name: str
    model_id: str
    messages: List[Dict[str, Any]]
    history_hint: str
    identity_prompt: str
    instruction_prompt: Optional[str]
    system_prompt: str


class GroupTurnContextBuilder:
    """Builds prompts/messages for one group assistant turn."""

    def __init__(
        self,
        *,
        storage: Any,
        memory_service: Any,
        build_rag_context_and_sources: Callable[..., Awaitable[Tuple[Optional[str], List[Dict[str, Any]]]]],
        build_group_history_hint: Callable[[List[Dict[str, Any]], str, Dict[str, str]], str],
        build_group_identity_prompt: Callable[[str, str, List[str], Dict[str, str]], str],
        build_group_instruction_prompt: Callable[[Optional[str], Optional[Dict[str, Any]]], Optional[str]],
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
        group_assistants: List[str],
        assistant_name_map: Dict[str, str],
        raw_user_message: str,
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        instruction: Optional[str] = None,
        committee_turn_packet: Optional[Dict[str, Any]] = None,
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
        try:
            memory_context, _ = self.memory_service.build_memory_context(
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

        rag_context, _ = await self.build_rag_context_and_sources(
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

        return GroupTurnContext(
            assistant_name=assistant_name,
            model_id=model_id,
            messages=messages,
            history_hint=history_hint,
            identity_prompt=identity_prompt,
            instruction_prompt=instruction_prompt,
            system_prompt=system_prompt,
        )
