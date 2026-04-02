"""Round-robin orchestration loop over group participants."""

import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from src.application.chat.request_contexts import (
    CommitteeExecutionContext,
    CommitteeMemberTurnContext,
)
from src.application.orchestration import (
    ActorEmit,
    ActorExecutionContext,
    ActorRef,
    ActorResult,
    NodeSpec,
    OrchestrationEngine,
    RunContext,
    RunSpec,
)

from .base import (
    BaseChatOrchestrator,
    ChatOrchestrationCancelToken,
    ChatOrchestrationEvent,
    ChatOrchestrationRequest,
    RoundRobinSettings,
)
from .terminal import build_group_done_event, cancellation_reason


class RoundRobinOrchestrator(BaseChatOrchestrator):
    """Simple sequential orchestrator that iterates participants in fixed order."""

    mode = "round_robin"

    def __init__(
        self,
        *,
        stream_group_assistant_turn: Callable[..., AsyncIterator[dict[str, Any]]],
        orchestration_engine: OrchestrationEngine | None = None,
    ):
        self.stream_group_assistant_turn = stream_group_assistant_turn
        self.orchestration_engine = orchestration_engine or OrchestrationEngine()

    async def stream(
        self,
        request: ChatOrchestrationRequest,
        *,
        cancel_token: ChatOrchestrationCancelToken | None = None,
    ) -> AsyncIterator[ChatOrchestrationEvent]:
        if request.mode and request.mode != self.mode:
            raise ValueError(f"RoundRobinOrchestrator only supports mode={self.mode}")
        if request.settings is not None and not isinstance(request.settings, RoundRobinSettings):
            raise ValueError("RoundRobinOrchestrator requires RoundRobinSettings")
        run_id = f"round-robin-{request.session_id[:12]}-{uuid.uuid4().hex[:8]}"
        spec = RunSpec(
            run_id=run_id,
            entry_node_id="round_robin_driver",
            nodes=(
                NodeSpec(
                    node_id="round_robin_driver",
                    actor=ActorRef(
                        actor_id="round_robin_driver",
                        kind="round_robin",
                        handler=lambda ctx: self._run_round_robin_actor(
                            execution_context=ctx,
                            request=request,
                            cancel_token=cancel_token,
                        ),
                    ),
                ),
            ),
            metadata={"mode": self.mode, "session_id": request.session_id},
        )
        context = RunContext(run_id=run_id, max_steps=2)

        async for runtime_event in self.orchestration_engine.run_stream(spec, context):
            if (
                runtime_event.get("type") == "node_event"
                and runtime_event.get("event_type") == "round_robin_event"
            ):
                payload = runtime_event.get("payload") or {}
                event = payload.get("event") if isinstance(payload, dict) else None
                if isinstance(event, dict):
                    yield self.normalize_event(event)
                continue
            if runtime_event.get("type") in {"failed", "cancelled"}:
                yield self.normalize_event(
                    build_group_done_event(
                        mode=self.mode,
                        reason=str(
                            runtime_event.get("terminal_reason")
                            or cancellation_reason(cancel_token)
                        ),
                        rounds=0,
                    )
                )
                return

    async def _run_round_robin_actor(
        self,
        *,
        execution_context: ActorExecutionContext,
        request: ChatOrchestrationRequest,
        cancel_token: ChatOrchestrationCancelToken | None,
    ) -> AsyncIterator[Any]:
        settings = (
            request.settings
            if isinstance(request.settings, RoundRobinSettings)
            else RoundRobinSettings()
        )

        participant_order = [
            assistant_id
            for assistant_id in request.participants
            if assistant_id in request.assistant_config_map
        ]
        if settings.max_turns and settings.max_turns > 0:
            participant_order = participant_order[: settings.max_turns]

        completed_turns = 0
        execution = CommitteeExecutionContext.from_orchestration_request(request)
        for assistant_id in participant_order:
            if self.is_cancelled(cancel_token):
                done_event = build_group_done_event(
                    mode=self.mode,
                    reason=cancellation_reason(cancel_token),
                    rounds=completed_turns,
                )
                yield ActorEmit(event_type="round_robin_event", payload={"event": done_event})
                yield ActorResult(
                    terminal_status="completed",
                    terminal_reason=done_event.get("reason", "cancelled"),
                    payload={"rounds": completed_turns},
                )
                return

            assistant_obj = request.assistant_config_map.get(assistant_id)
            if not assistant_obj:
                continue

            async for event in self.stream_group_assistant_turn(
                turn_context=CommitteeMemberTurnContext(
                    execution=execution,
                    assistant_id=assistant_id,
                    assistant_obj=assistant_obj,
                    trace_mode=self.mode,
                ),
                trace_id=request.trace_id,
            ):
                yield ActorEmit(event_type="round_robin_event", payload={"event": event})
            completed_turns += 1

        done_event = build_group_done_event(
            mode=self.mode,
            reason="completed",
            rounds=completed_turns,
        )
        await execution_context.patch_context(
            namespace="group",
            payload={"completed_turns": completed_turns, "mode": self.mode},
        )
        yield ActorEmit(event_type="round_robin_event", payload={"event": done_event})
        yield ActorResult(
            terminal_status="completed",
            terminal_reason="completed",
            payload={"rounds": completed_turns},
        )
