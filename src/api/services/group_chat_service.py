"""Group chat execution service extracted from AgentService."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import uuid
from typing import AsyncIterator, Awaitable, Callable, Dict, List, Optional, Protocol, Tuple

from .chat_input_service import PreparedUserInput
from .group_orchestration import (
    CommitteeOrchestrator,
    OrchestrationRequest,
    ResolvedCommitteeSettings,
    ResolvedGroupSettings,
    RoundRobinOrchestrator,
    RoundRobinSettings,
)
from .service_contracts import (
    AssistantLike,
    SearchServiceLike,
    SourcePayload,
    StreamEvent,
)


logger = logging.getLogger(__name__)


class _ChatInputServiceLike(Protocol):
    async def prepare_user_input(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        expanded_user_message: str,
        attachments: Optional[List[SourcePayload]],
        skip_user_append: bool,
        context_type: str,
        project_id: Optional[str],
    ) -> PreparedUserInput: ...


class _PostTurnServiceLike(Protocol):
    async def schedule_title_generation(
        self,
        *,
        session_id: str,
        context_type: str,
        project_id: Optional[str],
    ) -> None: ...


@dataclass(frozen=True)
class GroupChatDeps:
    """Dependencies required by GroupChatService."""

    chat_input_service: _ChatInputServiceLike
    post_turn_service: _PostTurnServiceLike
    search_service: SearchServiceLike
    build_file_context_block: Callable[[Optional[List[Dict[str, str]]]], Awaitable[str]]
    build_group_runtime_assistant: Callable[[str], Awaitable[Optional[Tuple[str, AssistantLike, str]]]]
    resolve_group_settings: Callable[..., ResolvedGroupSettings]
    create_committee_orchestrator: Callable[[], CommitteeOrchestrator]
    create_round_robin_orchestrator: Callable[[], RoundRobinOrchestrator]
    is_group_trace_enabled: Callable[[], bool]
    log_group_trace: Callable[[str, str, Dict[str, object]], None]
    truncate_log_text: Callable[[Optional[str], int], str]
    group_trace_preview_chars: int


class GroupChatService:
    """Handles group chat runtime flow for round-robin and committee modes."""

    def __init__(self, deps: GroupChatDeps):
        self.deps = deps

    async def process_committee_group_message_stream(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        group_assistants: List[str],
        assistant_name_map: Dict[str, str],
        assistant_config_map: Dict[str, AssistantLike],
        group_settings: Optional[Dict[str, object]],
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[SourcePayload],
        trace_id: Optional[str] = None,
    ) -> AsyncIterator[StreamEvent]:
        """Committee mode orchestration: supervisor decides who speaks each round."""
        if trace_id is None and self.deps.is_group_trace_enabled():
            trace_id = f"{session_id[:8]}-{uuid.uuid4().hex[:6]}"

        resolved_settings = self.deps.resolve_group_settings(
            group_mode="committee",
            group_assistants=group_assistants,
            group_settings=group_settings,
            assistant_config_map=assistant_config_map,
        )
        committee_settings: Optional[ResolvedCommitteeSettings] = resolved_settings.committee
        if committee_settings is None:
            return

        orchestrator = self.deps.create_committee_orchestrator()
        request = OrchestrationRequest(
            session_id=session_id,
            mode="committee",
            user_message=raw_user_message,
            participants=group_assistants,
            assistant_name_map=assistant_name_map,
            assistant_config_map=assistant_config_map,
            settings=committee_settings,
            reasoning_effort=reasoning_effort,
            context_type=context_type,
            project_id=project_id,
            search_context=search_context,
            search_sources=search_sources,
            trace_id=trace_id,
        )
        async for event in orchestrator.stream(request):
            yield event

    async def process_group_message_stream(
        self,
        session_id: str,
        user_message: str,
        group_assistants: List[str],
        group_mode: str = "round_robin",
        group_settings: Optional[Dict[str, object]] = None,
        skip_user_append: bool = False,
        reasoning_effort: Optional[str] = None,
        attachments: Optional[List[SourcePayload]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream process user message with multiple assistants (group chat)."""
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

        group_assistants, assistant_name_map, assistant_config_map = await self._resolve_participants(
            group_assistants
        )
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
        async for event in self._stream_group_mode(
            session_id=session_id,
            raw_user_message=raw_user_message,
            group_mode=group_mode,
            group_assistants=group_assistants,
            assistant_name_map=assistant_name_map,
            assistant_config_map=assistant_config_map,
            group_settings=group_settings,
            reasoning_effort=reasoning_effort,
            context_type=context_type,
            project_id=project_id,
            search_context=search_context,
            search_sources=search_sources,
        ):
            yield event

        await self.deps.post_turn_service.schedule_title_generation(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def _resolve_participants(
        self,
        group_assistants: List[str],
    ) -> Tuple[List[str], Dict[str, str], Dict[str, AssistantLike]]:
        assistant_name_map: Dict[str, str] = {}
        assistant_config_map: Dict[str, AssistantLike] = {}
        resolved_group_assistants: List[str] = []
        seen_participants = set()
        for participant_token in group_assistants:
            resolved = await self.deps.build_group_runtime_assistant(participant_token)
            if not resolved:
                logger.warning(
                    "[GroupChat] Participant '%s' not found or disabled, skipping", participant_token
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
        search_query: Optional[str],
        raw_user_message: str,
    ) -> Tuple[Optional[str], List[SourcePayload]]:
        search_sources: List[SourcePayload] = []
        search_context = None
        if not use_web_search:
            return search_context, search_sources
        query = (search_query or raw_user_message).strip()
        if not query:
            return search_context, search_sources
        try:
            sources = await self.deps.search_service.search(query)
            search_sources = [s.model_dump() for s in sources]
            if sources:
                search_context = self.deps.search_service.build_search_context(query, sources)
        except Exception as e:
            logger.warning("[GroupChat] Web search failed: %s", e)
        return search_context, search_sources

    async def _stream_group_mode(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        group_mode: str,
        group_assistants: List[str],
        assistant_name_map: Dict[str, str],
        assistant_config_map: Dict[str, AssistantLike],
        group_settings: Optional[Dict[str, object]],
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[SourcePayload],
    ) -> AsyncIterator[StreamEvent]:
        normalized_group_mode = (group_mode or "round_robin").strip().lower()
        if normalized_group_mode == "committee":
            trace_id = self._build_committee_trace_id(
                session_id=session_id,
                raw_user_message=raw_user_message,
                group_mode=normalized_group_mode,
                group_assistants=group_assistants,
            )
            async for event in self.process_committee_group_message_stream(
                session_id=session_id,
                raw_user_message=raw_user_message,
                group_assistants=group_assistants,
                assistant_name_map=assistant_name_map,
                assistant_config_map=assistant_config_map,
                group_settings=group_settings,
                reasoning_effort=reasoning_effort,
                context_type=context_type,
                project_id=project_id,
                search_context=search_context,
                search_sources=search_sources,
                trace_id=trace_id,
            ):
                yield event
            return

        request = OrchestrationRequest(
            session_id=session_id,
            mode="round_robin",
            user_message=raw_user_message,
            participants=group_assistants,
            assistant_name_map=assistant_name_map,
            assistant_config_map=assistant_config_map,
            settings=RoundRobinSettings(),
            reasoning_effort=reasoning_effort,
            context_type=context_type,
            project_id=project_id,
            search_context=search_context,
            search_sources=search_sources,
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
        group_assistants: List[str],
    ) -> Optional[str]:
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
