"""Committee action execution helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from .base import ChatOrchestrationCancelToken
from .committee_types import CommitteeDecision, CommitteeRuntimeState, CommitteeTurnRecord
from .runtime import CommitteeRuntime
from .settings import ResolvedCommitteeSettings
from .supervisor import CommitteeSupervisor
from .terminal import build_group_done_event, cancellation_reason


@dataclass(frozen=True)
class CommitteeRunContext:
    """Static run context shared by committee action handlers."""

    session_id: str
    raw_user_message: str
    group_assistants: List[str]
    supervisor_id: str
    supervisor_name: str
    supervisor_obj: Any
    assistant_name_map: Dict[str, str]
    assistant_config_map: Dict[str, Any]
    reasoning_effort: Optional[str]
    context_type: str
    project_id: Optional[str]
    search_context: Optional[str]
    search_sources: List[Dict[str, Any]]
    committee_settings: ResolvedCommitteeSettings
    trace_id: Optional[str] = None


class CommitteeActionExecutor:
    """Executes committee actions while updating runtime state."""

    def __init__(
        self,
        *,
        mode: str,
        stream_group_assistant_turn: Callable[..., AsyncIterator[Dict[str, Any]]],
        get_message_content_by_id: Callable[..., Any],
        build_structured_turn_summary: Callable[[str], Dict[str, Any]],
        build_committee_turn_packet: Callable[..., Dict[str, Any]],
        detect_group_role_drift: Callable[..., Optional[str]],
        build_role_retry_instruction: Callable[..., str],
        truncate_log_text: Callable[[Optional[str], int], str],
        log_group_trace: Callable[[str, str, Dict[str, Any]], None],
        group_trace_preview_chars: int = 1600,
    ):
        self.mode = mode
        self.stream_group_assistant_turn = stream_group_assistant_turn
        self.get_message_content_by_id = get_message_content_by_id
        self.build_structured_turn_summary = build_structured_turn_summary
        self.build_committee_turn_packet = build_committee_turn_packet
        self.detect_group_role_drift = detect_group_role_drift
        self.build_role_retry_instruction = build_role_retry_instruction
        self.truncate_log_text = truncate_log_text
        self.log_group_trace = log_group_trace
        self.group_trace_preview_chars = group_trace_preview_chars

    async def execute(
        self,
        *,
        decision: CommitteeDecision,
        current_round: int,
        state: CommitteeRuntimeState,
        runtime: CommitteeRuntime,
        supervisor: CommitteeSupervisor,
        run_context: CommitteeRunContext,
        cancel_token: Optional[ChatOrchestrationCancelToken],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Dispatch action to the matching handler."""
        if decision.action == "finish":
            async for event in self._handle_finish_action(
                decision=decision,
                current_round=current_round,
                state=state,
                supervisor=supervisor,
                run_context=run_context,
                cancel_token=cancel_token,
            ):
                yield event
            return

        if decision.action == "parallel_speak":
            async for event in self._handle_parallel_speak_action(
                decision=decision,
                current_round=current_round,
                state=state,
                runtime=runtime,
                supervisor=supervisor,
                run_context=run_context,
                cancel_token=cancel_token,
            ):
                yield event
            return

        async for event in self._handle_speak_action(
            decision=decision,
            current_round=current_round,
            state=state,
            runtime=runtime,
            run_context=run_context,
            cancel_token=cancel_token,
        ):
            yield event

    async def stream_supervisor_summary(
        self,
        *,
        finish_reason: str,
        current_round: int,
        state: CommitteeRuntimeState,
        supervisor: CommitteeSupervisor,
        run_context: CommitteeRunContext,
        cancel_token: Optional[ChatOrchestrationCancelToken],
        draft_summary: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream final supervisor synthesis and emit canonical group_done event."""
        if self.is_cancelled(cancel_token):
            yield self.build_cancelled_event(state=state, cancel_token=cancel_token)
            return

        summary_instruction = supervisor.build_summary_instruction(
            state,
            reason=finish_reason,
            draft_summary=draft_summary,
        )
        summary_packet = self.build_committee_turn_packet(
            state=state,
            target_assistant_id=run_context.supervisor_id,
            assistant_name_map=run_context.assistant_name_map,
            instruction=summary_instruction,
        )
        async for event in self.stream_group_assistant_turn(
            session_id=run_context.session_id,
            assistant_id=run_context.supervisor_id,
            assistant_obj=run_context.supervisor_obj,
            group_assistants=run_context.group_assistants,
            assistant_name_map=run_context.assistant_name_map,
            raw_user_message=run_context.raw_user_message,
            reasoning_effort=run_context.reasoning_effort,
            context_type=run_context.context_type,
            project_id=run_context.project_id,
            search_context=run_context.search_context,
            search_sources=run_context.search_sources,
            instruction=summary_instruction,
            committee_turn_packet=summary_packet,
            trace_id=run_context.trace_id,
            trace_round=current_round,
            trace_mode=self.mode,
        ):
            yield event
        if run_context.trace_id:
            self.log_group_trace(
                run_context.trace_id,
                "committee_done",
                {
                    "reason": finish_reason,
                    "rounds": state.round_index,
                },
            )
        yield build_group_done_event(
            mode=self.mode,
            reason=finish_reason,
            rounds=state.round_index,
        )

    def build_cancelled_event(
        self,
        *,
        state: CommitteeRuntimeState,
        cancel_token: Optional[ChatOrchestrationCancelToken],
    ) -> Dict[str, Any]:
        """Build canonical cancellation terminal event."""
        return build_group_done_event(
            mode=self.mode,
            reason=cancellation_reason(cancel_token),
            rounds=state.round_index,
        )

    @staticmethod
    def is_cancelled(cancel_token: Optional[ChatOrchestrationCancelToken]) -> bool:
        return bool(cancel_token and cancel_token.is_cancelled)

    async def _handle_finish_action(
        self,
        *,
        decision: CommitteeDecision,
        current_round: int,
        state: CommitteeRuntimeState,
        supervisor: CommitteeSupervisor,
        run_context: CommitteeRunContext,
        cancel_token: Optional[ChatOrchestrationCancelToken],
    ) -> AsyncIterator[Dict[str, Any]]:
        finish_reason = decision.reason or "supervisor_finish"
        async for event in self.stream_supervisor_summary(
            finish_reason=finish_reason,
            current_round=current_round,
            state=state,
            supervisor=supervisor,
            draft_summary=decision.final_response,
            run_context=run_context,
            cancel_token=cancel_token,
        ):
            yield event

    async def _handle_parallel_speak_action(
        self,
        *,
        decision: CommitteeDecision,
        current_round: int,
        state: CommitteeRuntimeState,
        runtime: CommitteeRuntime,
        supervisor: CommitteeSupervisor,
        run_context: CommitteeRunContext,
        cancel_token: Optional[ChatOrchestrationCancelToken],
    ) -> AsyncIterator[Dict[str, Any]]:
        if self.is_cancelled(cancel_token):
            yield self.build_cancelled_event(state=state, cancel_token=cancel_token)
            return

        parallel_targets = [
            assistant_id
            for assistant_id in (decision.assistant_ids or [])
            if assistant_id in run_context.assistant_config_map
        ]
        if len(parallel_targets) < 2:
            fallback_target = (
                decision.assistant_id
                if decision.assistant_id in run_context.assistant_config_map
                else None
            )
            if not fallback_target and parallel_targets:
                fallback_target = parallel_targets[0]
            if not fallback_target:
                yield build_group_done_event(
                    mode=self.mode,
                    reason="invalid_parallel_targets",
                    rounds=state.round_index,
                )
                return
            decision.action = "speak"
            decision.assistant_id = fallback_target
            decision.assistant_ids = None
            async for event in self._handle_speak_action(
                decision=decision,
                current_round=current_round,
                state=state,
                runtime=runtime,
                run_context=run_context,
                cancel_token=cancel_token,
            ):
                yield event
            return

        event_queue: asyncio.Queue = asyncio.Queue()
        parallel_message_ids: Dict[str, Optional[str]] = {}
        parallel_errors: List[Dict[str, Any]] = []

        async def _run_parallel_target(target_id: str) -> None:
            target_obj = run_context.assistant_config_map[target_id]
            target_instruction = decision.instruction
            try:
                turn_packet = self.build_committee_turn_packet(
                    state=state,
                    target_assistant_id=target_id,
                    assistant_name_map=run_context.assistant_name_map,
                    instruction=target_instruction,
                )
                async for event in self.stream_group_assistant_turn(
                    session_id=run_context.session_id,
                    assistant_id=target_id,
                    assistant_obj=target_obj,
                    group_assistants=run_context.group_assistants,
                    assistant_name_map=run_context.assistant_name_map,
                    raw_user_message=run_context.raw_user_message,
                    reasoning_effort=run_context.reasoning_effort,
                    context_type=run_context.context_type,
                    project_id=run_context.project_id,
                    search_context=run_context.search_context,
                    search_sources=run_context.search_sources,
                    instruction=target_instruction,
                    committee_turn_packet=turn_packet,
                    trace_id=run_context.trace_id,
                    trace_round=current_round,
                    trace_mode=self.mode,
                ):
                    if event.get("type") == "assistant_message_id":
                        parallel_message_ids[target_id] = event.get("message_id")
                    await event_queue.put({"kind": "event", "event": event})
            except Exception as e:
                parallel_errors.append(
                    {
                        "assistant_id": target_id,
                        "assistant_name": run_context.assistant_name_map.get(target_id, target_id),
                        "error": str(e),
                    }
                )
                await event_queue.put(
                    {
                        "kind": "error",
                        "assistant_id": target_id,
                        "assistant_name": run_context.assistant_name_map.get(target_id, target_id),
                        "error": str(e),
                    }
                )
            finally:
                await event_queue.put({"kind": "done", "assistant_id": target_id})

        tasks = [
            asyncio.create_task(_run_parallel_target(target_id))
            for target_id in parallel_targets
        ]
        completed_targets = 0
        while completed_targets < len(tasks):
            if self.is_cancelled(cancel_token):
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                yield self.build_cancelled_event(state=state, cancel_token=cancel_token)
                return

            item = await event_queue.get()
            kind = item.get("kind")
            if kind == "event":
                yield item["event"]
            elif kind == "error":
                yield {
                    "type": "group_action",
                    "mode": self.mode,
                    "round": current_round,
                    "action": "parallel_error",
                    "assistant_id": item.get("assistant_id"),
                    "assistant_name": item.get("assistant_name"),
                    "reason": item.get("error"),
                    "supervisor_id": run_context.supervisor_id,
                    "supervisor_name": run_context.supervisor_name,
                }
            elif kind == "done":
                completed_targets += 1

        await asyncio.gather(*tasks, return_exceptions=True)

        successful_targets = [
            target_id for target_id in parallel_targets if parallel_message_ids.get(target_id)
        ]
        if not successful_targets:
            yield build_group_done_event(
                mode=self.mode,
                reason="parallel_speak_failed",
                rounds=state.round_index,
            )
            return

        for target_id in successful_targets:
            target_message_id = parallel_message_ids.get(target_id)
            await self._record_turn_from_message(
                state=state,
                session_id=run_context.session_id,
                message_id=target_message_id,
                assistant_id=target_id,
                assistant_name=run_context.assistant_name_map.get(target_id, target_id),
                context_type=run_context.context_type,
                project_id=run_context.project_id,
                runtime=runtime,
            )

        if parallel_errors and run_context.trace_id:
            self.log_group_trace(
                run_context.trace_id,
                "parallel_speak_errors",
                {
                    "round": current_round,
                    "errors": parallel_errors,
                },
            )
        runtime.advance_round(state)

    async def _handle_speak_action(
        self,
        *,
        decision: CommitteeDecision,
        current_round: int,
        state: CommitteeRuntimeState,
        runtime: CommitteeRuntime,
        run_context: CommitteeRunContext,
        cancel_token: Optional[ChatOrchestrationCancelToken],
    ) -> AsyncIterator[Dict[str, Any]]:
        if self.is_cancelled(cancel_token):
            yield self.build_cancelled_event(state=state, cancel_token=cancel_token)
            return

        target_id = decision.assistant_id
        if not target_id:
            yield build_group_done_event(
                mode=self.mode,
                reason="invalid_speak_target",
                rounds=state.round_index,
            )
            return
        target_obj = run_context.assistant_config_map.get(target_id)
        if not target_obj:
            yield build_group_done_event(
                mode=self.mode,
                reason="invalid_speak_target",
                rounds=state.round_index,
            )
            return

        target_message_id: Optional[str] = None
        content = ""
        role_retry_limit = run_context.committee_settings.role_retry_limit
        turn_instruction = decision.instruction
        for attempt in range(role_retry_limit + 1):
            if self.is_cancelled(cancel_token):
                yield self.build_cancelled_event(state=state, cancel_token=cancel_token)
                return

            target_message_id = None
            turn_packet = self.build_committee_turn_packet(
                state=state,
                target_assistant_id=target_id,
                assistant_name_map=run_context.assistant_name_map,
                instruction=turn_instruction,
            )
            async for event in self.stream_group_assistant_turn(
                session_id=run_context.session_id,
                assistant_id=target_id,
                assistant_obj=target_obj,
                group_assistants=run_context.group_assistants,
                assistant_name_map=run_context.assistant_name_map,
                raw_user_message=run_context.raw_user_message,
                reasoning_effort=run_context.reasoning_effort,
                context_type=run_context.context_type,
                project_id=run_context.project_id,
                search_context=run_context.search_context,
                search_sources=run_context.search_sources,
                instruction=turn_instruction,
                committee_turn_packet=turn_packet,
                trace_id=run_context.trace_id,
                trace_round=current_round,
                trace_mode=self.mode,
            ):
                if event.get("type") == "assistant_message_id":
                    target_message_id = event.get("message_id")
                yield event

            content = await self.get_message_content_by_id(
                session_id=run_context.session_id,
                message_id=target_message_id,
                context_type=run_context.context_type,
                project_id=run_context.project_id,
            )
            drift_reason = self.detect_group_role_drift(
                content=content,
                expected_assistant_id=target_id,
                expected_assistant_name=run_context.assistant_name_map.get(target_id, target_id),
                participant_name_map=run_context.assistant_name_map,
            )
            if drift_reason and attempt < role_retry_limit:
                turn_instruction = self.build_role_retry_instruction(
                    base_instruction=decision.instruction,
                    expected_assistant_name=run_context.assistant_name_map.get(target_id, target_id),
                )
                yield {
                    "type": "group_action",
                    "mode": self.mode,
                    "round": current_round,
                    "action": "role_retry",
                    "assistant_id": target_id,
                    "assistant_name": run_context.assistant_name_map.get(target_id, target_id),
                    "reason": drift_reason,
                    "supervisor_id": run_context.supervisor_id,
                    "supervisor_name": run_context.supervisor_name,
                }
                if run_context.trace_id:
                    self.log_group_trace(
                        run_context.trace_id,
                        "role_retry",
                        {
                            "round": current_round,
                            "assistant_id": target_id,
                            "assistant_name": run_context.assistant_name_map.get(target_id, target_id),
                            "reason": drift_reason,
                            "previous_response_preview": self.truncate_log_text(
                                content, self.group_trace_preview_chars
                            ),
                            "retry_instruction": self.truncate_log_text(
                                turn_instruction, self.group_trace_preview_chars
                            ),
                            "turn_packet": turn_packet,
                        },
                    )
                continue
            break

        structured_turn = self.build_structured_turn_summary(content)
        runtime.record_turn(
            state,
            CommitteeTurnRecord(
                assistant_id=target_id,
                assistant_name=run_context.assistant_name_map.get(target_id, target_id),
                message_id=target_message_id,
                content_preview=(structured_turn.get("content_preview") or "")[:240],
                key_points=structured_turn.get("key_points", []),
                risks=structured_turn.get("risks", []),
                actions=structured_turn.get("actions", []),
                self_summary=structured_turn.get("self_summary", ""),
            ),
        )
        runtime.advance_round(state)

    async def _record_turn_from_message(
        self,
        *,
        state: CommitteeRuntimeState,
        session_id: str,
        message_id: Optional[str],
        assistant_id: str,
        assistant_name: str,
        context_type: str,
        project_id: Optional[str],
        runtime: CommitteeRuntime,
    ) -> None:
        content = await self.get_message_content_by_id(
            session_id=session_id,
            message_id=message_id,
            context_type=context_type,
            project_id=project_id,
        )
        structured_turn = self.build_structured_turn_summary(content)
        runtime.record_turn(
            state,
            CommitteeTurnRecord(
                assistant_id=assistant_id,
                assistant_name=assistant_name,
                message_id=message_id,
                content_preview=(structured_turn.get("content_preview") or "")[:240],
                key_points=structured_turn.get("key_points", []),
                risks=structured_turn.get("risks", []),
                actions=structured_turn.get("actions", []),
                self_summary=structured_turn.get("self_summary", ""),
            ),
        )
