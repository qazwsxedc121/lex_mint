"""Round-robin orchestration loop over group participants."""

from typing import Any, AsyncIterator, Callable, Dict, Optional

from .base import (
    BaseOrchestrator,
    OrchestrationCancelToken,
    OrchestrationEvent,
    OrchestrationRequest,
    RoundRobinSettings,
)


class RoundRobinOrchestrator(BaseOrchestrator):
    """Simple sequential orchestrator that iterates participants in fixed order."""

    mode = "round_robin"

    def __init__(
        self,
        *,
        stream_group_assistant_turn: Callable[..., AsyncIterator[Dict[str, Any]]],
    ):
        self.stream_group_assistant_turn = stream_group_assistant_turn

    async def stream(
        self,
        request: OrchestrationRequest,
        *,
        cancel_token: Optional[OrchestrationCancelToken] = None,
    ) -> AsyncIterator[OrchestrationEvent]:
        if request.mode and request.mode != self.mode:
            raise ValueError(f"RoundRobinOrchestrator only supports mode={self.mode}")
        if request.settings is not None and not isinstance(request.settings, RoundRobinSettings):
            raise ValueError("RoundRobinOrchestrator requires RoundRobinSettings")
        settings = request.settings if isinstance(request.settings, RoundRobinSettings) else RoundRobinSettings()

        participant_order = [
            assistant_id
            for assistant_id in request.participants
            if assistant_id in request.assistant_config_map
        ]
        if settings.max_turns and settings.max_turns > 0:
            participant_order = participant_order[: settings.max_turns]

        for assistant_id in participant_order:
            if self.is_cancelled(cancel_token):
                return

            assistant_obj = request.assistant_config_map.get(assistant_id)
            if not assistant_obj:
                continue

            async for event in self.stream_group_assistant_turn(
                session_id=request.session_id,
                assistant_id=assistant_id,
                assistant_obj=assistant_obj,
                group_assistants=request.participants,
                assistant_name_map=request.assistant_name_map,
                raw_user_message=request.user_message,
                reasoning_effort=request.reasoning_effort,
                context_type=request.context_type,
                project_id=request.project_id,
                search_context=request.search_context,
                search_sources=request.search_sources,
                trace_id=request.trace_id,
                trace_mode=self.mode,
            ):
                yield self.normalize_event(event)
