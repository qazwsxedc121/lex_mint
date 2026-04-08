"""Group chat execution service."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from src.application.chat.chat_input_service import PreparedUserInput
from src.application.chat.chat_runtime import (
    ChatOrchestrationCancelToken,
    ChatOrchestrationEvent,
    ChatOrchestrationRequest,
    ResolvedCommitteeSettings,
    ResolvedGroupSettings,
    RoundRobinSettings,
)
from src.application.chat.request_contexts import CommitteeExecutionContext, GroupChatRequestContext
from src.application.chat.service_contracts import (
    AssistantLike,
    SearchServiceLike,
    SourcePayload,
    StreamEvent,
)
from src.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)


class _ChatInputServiceLike(Protocol):
    async def prepare_user_input(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        expanded_user_message: str,
        attachments: list[SourcePayload] | None,
        skip_user_append: bool,
        context_type: str,
        project_id: str | None,
    ) -> PreparedUserInput: ...


class _PostTurnServiceLike(Protocol):
    async def schedule_title_generation(
        self,
        *,
        session_id: str,
        context_type: str,
        project_id: str | None,
    ) -> None: ...


class _CommitteeOrchestratorLike(Protocol):
    def stream(
        self,
        request: ChatOrchestrationRequest,
        *,
        cancel_token: ChatOrchestrationCancelToken | None = None,
    ) -> AsyncIterator[ChatOrchestrationEvent]: ...


class _RoundRobinOrchestratorLike(Protocol):
    def stream(
        self,
        request: ChatOrchestrationRequest,
        *,
        cancel_token: ChatOrchestrationCancelToken | None = None,
    ) -> AsyncIterator[ChatOrchestrationEvent]: ...


@dataclass(frozen=True)
class GroupChatDeps:
    """Dependencies required by GroupChatService."""

    chat_input_service: _ChatInputServiceLike
    post_turn_service: _PostTurnServiceLike
    search_service: SearchServiceLike
    build_file_context_block: Callable[[list[dict[str, str]] | None], Awaitable[str]]
    build_group_runtime_assistant: Callable[[str], Awaitable[tuple[str, AssistantLike, str] | None]]
    resolve_group_settings: Callable[..., ResolvedGroupSettings]
    create_committee_orchestrator: Callable[[], _CommitteeOrchestratorLike]
    create_round_robin_orchestrator: Callable[[], _RoundRobinOrchestratorLike]
    is_group_trace_enabled: Callable[[], bool]
    log_group_trace: Callable[[str, str, dict[str, object]], None]
    truncate_log_text: Callable[[str | None, int], str]
    group_trace_preview_chars: int


class GroupChatService:
    """Handles group chat runtime flow for round-robin and committee modes."""

    def __init__(self, deps: GroupChatDeps):
        self.deps = deps

    async def process_committee_group_message_stream(
        self,
        *,
        request: CommitteeExecutionContext,
    ) -> AsyncIterator[StreamEvent]:
        """Committee mode orchestration: supervisor decides who speaks each round."""
        session_id = request.scope.session_id
        trace_id = request.trace_id
        if trace_id is None and self.deps.is_group_trace_enabled():
            trace_id = f"{session_id[:8]}-{uuid.uuid4().hex[:6]}"

        resolved_settings = self.deps.resolve_group_settings(
            group_mode="committee",
            group_assistants=request.group_assistants,
            group_settings=request.group_settings,
            assistant_config_map=request.assistant_config_map,
        )
        committee_settings: ResolvedCommitteeSettings | None = resolved_settings.committee
        if committee_settings is None:
            return

        orchestrator = self.deps.create_committee_orchestrator()
        orchestration_request = request.to_orchestration_request(
            mode="committee",
            settings=committee_settings,
            trace_id=trace_id,
        )
        async for event in orchestrator.stream(orchestration_request):
            yield event

    async def process_group_message_stream(
        self,
        *,
        request: GroupChatRequestContext,
    ) -> AsyncIterator[StreamEvent]:
        """Stream process user message with multiple assistants (group chat)."""
        session_id = request.scope.session_id
        context_type = request.scope.context_type
        project_id = request.scope.project_id
        user_message = request.user_input.user_message
        attachments = request.user_input.attachments
        file_references = request.user_input.file_references
        group_assistants = request.group_assistants
        group_mode = request.group_mode
        group_settings = request.group_settings
        skip_user_append = request.stream.skip_user_append
        reasoning_effort = request.stream.reasoning_effort
        use_web_search = request.search.use_web_search
        search_query = request.search.search_query

        original_user_message = user_message
        file_context_block = await self.deps.build_file_context_block(file_references)
        if file_context_block:
            user_message = f"{file_context_block}\n\n{user_message}"

        prepared_input = await self.deps.chat_input_service.prepare_user_input(
            session_id=session_id,
            raw_user_message=original_user_message,
            expanded_user_message=user_message,
            attachments=attachments,
            skip_user_append=skip_user_append,
            context_type=context_type,
            project_id=project_id,
        )
        raw_user_message = prepared_input.raw_user_message
        if prepared_input.user_message_id:
            yield {"type": "user_message_id", "message_id": prepared_input.user_message_id}

        (
            group_assistants,
            assistant_name_map,
            assistant_config_map,
        ) = await self._resolve_participants(group_assistants)
        if not group_assistants:
            yield {
                "type": "group_done",
                "mode": (group_mode or "round_robin").strip().lower(),
                "reason": "no_valid_participants",
                "rounds": 0,
            }
            return

        search_context, search_sources = await self._build_optional_search_context(
            use_web_search=use_web_search,
            search_query=search_query,
            raw_user_message=raw_user_message,
        )
        execution_context = CommitteeExecutionContext(
            scope=request.scope,
            raw_user_message=raw_user_message,
            group_assistants=group_assistants,
            assistant_name_map=assistant_name_map,
            assistant_config_map=assistant_config_map,
            group_settings=group_settings,
            reasoning_effort=reasoning_effort,
            search_context=search_context,
            search_sources=search_sources,
            group_mode=group_mode,
        )
        async for event in self._stream_group_mode(
            execution_context=execution_context,
        ):
            yield event

        await self.deps.post_turn_service.schedule_title_generation(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def _resolve_participants(
        self,
        group_assistants: list[str],
    ) -> tuple[list[str], dict[str, str], dict[str, AssistantLike]]:
        assistant_name_map: dict[str, str] = {}
        assistant_config_map: dict[str, AssistantLike] = {}
        resolved_group_assistants: list[str] = []
        seen_participants = set()
        for participant_token in group_assistants:
            resolved = await self.deps.build_group_runtime_assistant(participant_token)
            if not resolved:
                logger.warning(
                    "[GroupChat] Participant '%s' not found or disabled, skipping",
                    participant_token,
                )
                continue
            participant_id, participant_obj, participant_name = resolved
            if participant_id in seen_participants:
                continue
            seen_participants.add(participant_id)
            resolved_group_assistants.append(participant_id)
            assistant_config_map[participant_id] = participant_obj
            assistant_name_map[participant_id] = participant_name
        return resolved_group_assistants, assistant_name_map, assistant_config_map

    async def _build_optional_search_context(
        self,
        *,
        use_web_search: bool,
        search_query: str | None,
        raw_user_message: str,
    ) -> tuple[str | None, list[SourcePayload]]:
        search_sources: list[SourcePayload] = []
        search_context = None
        if not use_web_search or not get_tool_registry().get_tool_names_by_group("web"):
            return search_context, search_sources
        query = (search_query or raw_user_message).strip()
        if not query:
            return search_context, search_sources
        try:
            sources = await self.deps.search_service.search(query)
            search_sources = [s.model_dump() for s in sources]
            if sources:
                search_context = self.deps.search_service.build_search_context(query, sources)
        except Exception as exc:
            logger.warning("[GroupChat] Web search failed: %s", exc)
        return search_context, search_sources

    async def _stream_group_mode(
        self,
        *,
        execution_context: CommitteeExecutionContext,
    ) -> AsyncIterator[StreamEvent]:
        normalized_group_mode = (execution_context.group_mode or "round_robin").strip().lower()
        if normalized_group_mode == "committee":
            trace_id = self._build_committee_trace_id(
                session_id=execution_context.scope.session_id,
                raw_user_message=execution_context.raw_user_message,
                group_mode=normalized_group_mode,
                group_assistants=execution_context.group_assistants,
            )
            async for event in self.process_committee_group_message_stream(
                request=execution_context.with_updates(
                    group_mode=normalized_group_mode,
                    trace_id=trace_id,
                ),
            ):
                yield event
            return

        request = execution_context.to_orchestration_request(
            mode="round_robin",
            settings=RoundRobinSettings(),
        )
        round_robin_orchestrator = self.deps.create_round_robin_orchestrator()
        async for event in round_robin_orchestrator.stream(request):
            yield event

    def _build_committee_trace_id(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        group_mode: str,
        group_assistants: list[str],
    ) -> str | None:
        if not self.deps.is_group_trace_enabled():
            return None
        trace_id = f"{session_id[:8]}-{uuid.uuid4().hex[:6]}"
        self.deps.log_group_trace(
            trace_id,
            "request",
            {
                "session_id": session_id,
                "group_mode": group_mode,
                "group_assistants": group_assistants,
                "raw_user_message": self.deps.truncate_log_text(
                    raw_user_message,
                    self.deps.group_trace_preview_chars,
                ),
            },
        )
        return trace_id
