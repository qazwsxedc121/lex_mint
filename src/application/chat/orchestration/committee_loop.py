"""Committee orchestration loop state machine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Optional

from .base import OrchestrationCancelToken
from .committee_types import CommitteeDecision, CommitteeRuntimeState
from .runtime import CommitteeRuntime


DecideRoundFn = Callable[[int, CommitteeRuntimeState], Awaitable[CommitteeDecision]]
ExecuteActionFn = Callable[[CommitteeDecision, int], AsyncIterator[Dict[str, Any]]]
BuildCancelledFn = Callable[..., Dict[str, Any]]


@dataclass(frozen=True)
class CommitteeLoopContext:
    """Static context shared by committee loop iterations."""

    mode: str
    max_rounds: int
    supervisor_id: str
    supervisor_name: str
    assistant_name_map: Dict[str, str]
    trace_id: Optional[str] = None


class CommitteeLoopStateMachine:
    """Runs committee round progression independent from action implementations."""

    def __init__(
        self,
        *,
        log_group_trace: Callable[[str, str, Dict[str, Any]], None],
        truncate_log_text: Callable[[Optional[str], int], str],
    ):
        self.log_group_trace = log_group_trace
        self.truncate_log_text = truncate_log_text

    async def run(
        self,
        *,
        runtime: CommitteeRuntime,
        state: CommitteeRuntimeState,
        context: CommitteeLoopContext,
        cancel_token: Optional[OrchestrationCancelToken],
        decide_round: DecideRoundFn,
        execute_action: ExecuteActionFn,
        build_cancelled_event: BuildCancelledFn,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Run committee rounds until terminated, canceled, or round-limit reached."""
        while runtime.has_remaining_rounds(state):
            if self.is_cancelled(cancel_token):
                yield build_cancelled_event(state=state, cancel_token=cancel_token)
                return

            current_round = runtime.current_round(state)
            self._log_round_state(
                trace_id=context.trace_id,
                current_round=current_round,
                state=state,
            )
            yield {
                "type": "group_round_start",
                "mode": context.mode,
                "round": current_round,
                "max_rounds": context.max_rounds,
                "supervisor_id": context.supervisor_id,
                "supervisor_name": context.supervisor_name,
            }

            decision = await decide_round(current_round, state)
            action_event = self._build_action_event(
                context=context,
                decision=decision,
                current_round=current_round,
            )
            yield action_event
            if context.trace_id:
                self.log_group_trace(
                    context.trace_id,
                    "supervisor_decision",
                    {
                        "round": current_round,
                        "action_event": action_event,
                    },
                )

            terminated = False
            async for event in execute_action(decision, current_round):
                if event.get("type") == "group_done":
                    terminated = True
                yield event
            if terminated:
                return

    @staticmethod
    def is_cancelled(cancel_token: Optional[OrchestrationCancelToken]) -> bool:
        return bool(cancel_token and cancel_token.is_cancelled)

    def _log_round_state(
        self,
        *,
        trace_id: Optional[str],
        current_round: int,
        state: CommitteeRuntimeState,
    ) -> None:
        if not trace_id:
            return
        self.log_group_trace(
            trace_id,
            "round_state",
            {
                "round": current_round,
                "turns_so_far": [
                    {
                        "assistant_id": turn.assistant_id,
                        "assistant_name": turn.assistant_name,
                        "message_id": turn.message_id,
                        "content_preview": self.truncate_log_text(turn.content_preview, 260),
                        "key_points": turn.key_points[:3],
                        "risks": turn.risks[:2],
                        "actions": turn.actions[:2],
                        "self_summary": turn.self_summary,
                    }
                    for turn in state.turns
                ],
            },
        )

    def _build_action_event(
        self,
        *,
        context: CommitteeLoopContext,
        decision: CommitteeDecision,
        current_round: int,
    ) -> Dict[str, Any]:
        action_event: Dict[str, Any] = {
            "type": "group_action",
            "mode": context.mode,
            "round": current_round,
            "action": decision.action,
            "reason": decision.reason,
            "supervisor_id": context.supervisor_id,
            "supervisor_name": context.supervisor_name,
        }
        if decision.assistant_id:
            action_event["assistant_id"] = decision.assistant_id
            action_event["assistant_name"] = context.assistant_name_map.get(
                decision.assistant_id, decision.assistant_id
            )
        if decision.assistant_ids:
            action_event["assistant_ids"] = decision.assistant_ids
            action_event["assistant_names"] = [
                context.assistant_name_map.get(assistant_id, assistant_id)
                for assistant_id in decision.assistant_ids
            ]
        if decision.instruction:
            action_event["instruction"] = decision.instruction
        return action_event
