"""Committee orchestration loop extracted from AgentService."""

import asyncio
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from .base import (
    BaseOrchestrator,
    OrchestrationCancelToken,
    OrchestrationEvent,
    OrchestrationRequest,
)
from .runtime import CommitteeRuntime
from .settings import ResolvedCommitteeSettings
from .supervisor import CommitteeSupervisor
from .types import CommitteeDecision, CommitteeRuntimeConfig, CommitteeRuntimeState, CommitteeTurnRecord


class CommitteeOrchestrator(BaseOrchestrator):
    """Runs committee rounds and emits group events without owning business services."""

    mode = "committee"

    def __init__(
        self,
        *,
        llm_call: Callable[..., str],
        assistant_params_from_config: Callable[[Any], Dict[str, Any]],
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
        self.llm_call = llm_call
        self.assistant_params_from_config = assistant_params_from_config
        self.stream_group_assistant_turn = stream_group_assistant_turn
        self.get_message_content_by_id = get_message_content_by_id
        self.build_structured_turn_summary = build_structured_turn_summary
        self.build_committee_turn_packet = build_committee_turn_packet
        self.detect_group_role_drift = detect_group_role_drift
        self.build_role_retry_instruction = build_role_retry_instruction
        self.truncate_log_text = truncate_log_text
        self.log_group_trace = log_group_trace
        self.group_trace_preview_chars = group_trace_preview_chars

    async def stream(
        self,
        request: OrchestrationRequest,
        *,
        cancel_token: Optional[OrchestrationCancelToken] = None,
    ) -> AsyncIterator[OrchestrationEvent]:
        """Mode-agnostic interface used by orchestrator callers."""
        if request.mode and request.mode != self.mode:
            raise ValueError(f"CommitteeOrchestrator only supports mode={self.mode}")
        if not isinstance(request.settings, ResolvedCommitteeSettings):
            raise ValueError("CommitteeOrchestrator requires ResolvedCommitteeSettings")

        async for event in self.process(
            session_id=request.session_id,
            raw_user_message=request.user_message,
            group_assistants=request.participants,
            committee_settings=request.settings,
            assistant_name_map=request.assistant_name_map,
            assistant_config_map=request.assistant_config_map,
            reasoning_effort=request.reasoning_effort,
            context_type=request.context_type,
            project_id=request.project_id,
            search_context=request.search_context,
            search_sources=request.search_sources,
            trace_id=request.trace_id,
            cancel_token=cancel_token,
        ):
            yield self.normalize_event(event)

    async def process(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        group_assistants: List[str],
        committee_settings: ResolvedCommitteeSettings,
        assistant_name_map: Dict[str, str],
        assistant_config_map: Dict[str, Any],
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[Dict[str, Any]],
        trace_id: Optional[str] = None,
        cancel_token: Optional[OrchestrationCancelToken] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Committee mode orchestration: supervisor decides who speaks each round."""
        participant_order = [
            assistant_id
            for assistant_id in group_assistants
            if assistant_id in assistant_config_map
        ]
        if not participant_order:
            yield {
                "type": "group_done",
                "mode": self.mode,
                "reason": "no_valid_participants",
                "rounds": 0,
            }
            return

        supervisor_id = committee_settings.supervisor_id
        if supervisor_id not in participant_order:
            supervisor_id = participant_order[0]
        supervisor_obj = assistant_config_map.get(supervisor_id)
        if supervisor_obj is None:
            supervisor_id = participant_order[0]
            supervisor_obj = assistant_config_map[supervisor_id]

        supervisor_name = assistant_name_map.get(supervisor_id, supervisor_id)
        max_rounds = committee_settings.max_rounds

        if trace_id:
            self.log_group_trace(
                trace_id,
                "committee_start",
                {
                    "session_id": session_id,
                    "supervisor_id": supervisor_id,
                    "supervisor_name": supervisor_name,
                    "participant_order": participant_order,
                    "max_rounds": max_rounds,
                    "min_member_turns_before_finish": committee_settings.min_member_turns_before_finish,
                    "min_total_rounds_before_finish": committee_settings.min_total_rounds_before_finish,
                    "max_parallel_speakers": committee_settings.max_parallel_speakers,
                    "role_retry_limit": committee_settings.role_retry_limit,
                    "allow_parallel_speak": committee_settings.allow_parallel_speak,
                    "allow_finish": committee_settings.allow_finish,
                    "fallback_notes": committee_settings.fallback_notes,
                    "user_message": self.truncate_log_text(
                        raw_user_message, self.group_trace_preview_chars
                    ),
                },
            )

        runtime = CommitteeRuntime(
            CommitteeRuntimeConfig(supervisor_id=supervisor_id, max_rounds=max_rounds)
        )
        state = CommitteeRuntimeState(
            user_message=raw_user_message,
            participants={
                assistant_id: assistant_name_map.get(assistant_id, assistant_id)
                for assistant_id in participant_order
            },
        )
        supervisor = CommitteeSupervisor(
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            participant_order=participant_order,
            participant_names=state.participants,
            max_rounds=max_rounds,
            min_member_turns_before_finish=committee_settings.min_member_turns_before_finish,
            min_total_rounds_before_finish=committee_settings.min_total_rounds_before_finish,
            max_parallel_speakers=committee_settings.max_parallel_speakers,
            allow_parallel_speak=committee_settings.allow_parallel_speak,
            allow_finish=committee_settings.allow_finish,
            supervisor_system_prompt_template=committee_settings.supervisor_system_prompt_template,
            summary_instruction_template=committee_settings.summary_instruction_template,
        )

        supervisor_call_context: Dict[str, Any] = {"round": None}

        async def _call_supervisor(system_prompt: str, user_prompt: str) -> str:
            assistant_params = self.assistant_params_from_config(supervisor_obj)
            if trace_id:
                self.log_group_trace(
                    trace_id,
                    "supervisor_request",
                    {
                        "round": supervisor_call_context.get("round"),
                        "supervisor_id": supervisor_id,
                        "model_id": supervisor_obj.model_id,
                        "system_prompt": self.truncate_log_text(
                            system_prompt, self.group_trace_preview_chars
                        ),
                        "user_prompt": self.truncate_log_text(
                            user_prompt, self.group_trace_preview_chars
                        ),
                    },
                )
            raw_output = await asyncio.to_thread(
                self.llm_call,
                [{"role": "user", "content": user_prompt}],
                session_id=session_id,
                model_id=supervisor_obj.model_id,
                system_prompt=system_prompt,
                **assistant_params,
            )
            if trace_id:
                self.log_group_trace(
                    trace_id,
                    "supervisor_raw_output",
                    {
                        "round": supervisor_call_context.get("round"),
                        "raw_output": self.truncate_log_text(
                            raw_output, self.group_trace_preview_chars
                        ),
                    },
                )
            return raw_output

        action_handlers = {
            "finish": self._handle_finish_action,
            "parallel_speak": self._handle_parallel_speak_action,
            "speak": self._handle_speak_action,
        }

        while runtime.has_remaining_rounds(state):
            if self.is_cancelled(cancel_token):
                yield self._build_cancelled_event(state=state, cancel_token=cancel_token)
                return

            current_round = runtime.current_round(state)
            supervisor_call_context["round"] = current_round
            if trace_id:
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
            yield {
                "type": "group_round_start",
                "mode": self.mode,
                "round": current_round,
                "max_rounds": max_rounds,
                "supervisor_id": supervisor_id,
                "supervisor_name": supervisor_name,
            }
            decision = await supervisor.decide(state, _call_supervisor)

            action_event: Dict[str, Any] = {
                "type": "group_action",
                "mode": self.mode,
                "round": current_round,
                "action": decision.action,
                "reason": decision.reason,
                "supervisor_id": supervisor_id,
                "supervisor_name": supervisor_name,
            }
            if decision.assistant_id:
                action_event["assistant_id"] = decision.assistant_id
                action_event["assistant_name"] = assistant_name_map.get(
                    decision.assistant_id, decision.assistant_id
                )
            if decision.assistant_ids:
                action_event["assistant_ids"] = decision.assistant_ids
                action_event["assistant_names"] = [
                    assistant_name_map.get(assistant_id, assistant_id)
                    for assistant_id in decision.assistant_ids
                ]
            if decision.instruction:
                action_event["instruction"] = decision.instruction
            yield action_event
            if trace_id:
                self.log_group_trace(
                    trace_id,
                    "supervisor_decision",
                    {
                        "round": current_round,
                        "action_event": action_event,
                    },
                )

            handler = action_handlers.get(decision.action, self._handle_speak_action)
            terminated = False
            async for event in handler(
                decision=decision,
                current_round=current_round,
                state=state,
                runtime=runtime,
                session_id=session_id,
                raw_user_message=raw_user_message,
                group_assistants=group_assistants,
                supervisor_id=supervisor_id,
                supervisor_name=supervisor_name,
                supervisor_obj=supervisor_obj,
                supervisor=supervisor,
                assistant_name_map=assistant_name_map,
                assistant_config_map=assistant_config_map,
                reasoning_effort=reasoning_effort,
                context_type=context_type,
                project_id=project_id,
                search_context=search_context,
                search_sources=search_sources,
                committee_settings=committee_settings,
                trace_id=trace_id,
                cancel_token=cancel_token,
            ):
                if event.get("type") == "group_done":
                    terminated = True
                yield event
            if terminated:
                return

        if self.is_cancelled(cancel_token):
            yield self._build_cancelled_event(state=state, cancel_token=cancel_token)
            return

        async for event in self._stream_supervisor_summary(
            finish_reason="max_rounds_reached",
            current_round=runtime.current_round(state),
            state=state,
            supervisor=supervisor,
            session_id=session_id,
            raw_user_message=raw_user_message,
            group_assistants=group_assistants,
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            supervisor_obj=supervisor_obj,
            assistant_name_map=assistant_name_map,
            reasoning_effort=reasoning_effort,
            context_type=context_type,
            project_id=project_id,
            search_context=search_context,
            search_sources=search_sources,
            trace_id=trace_id,
            cancel_token=cancel_token,
        ):
            yield event

    async def _handle_finish_action(
        self,
        *,
        decision: CommitteeDecision,
        current_round: int,
        state: CommitteeRuntimeState,
        runtime: CommitteeRuntime,
        session_id: str,
        raw_user_message: str,
        group_assistants: List[str],
        supervisor_id: str,
        supervisor_name: str,
        supervisor_obj: Any,
        supervisor: CommitteeSupervisor,
        assistant_name_map: Dict[str, str],
        assistant_config_map: Dict[str, Any],
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[Dict[str, Any]],
        committee_settings: ResolvedCommitteeSettings,
        trace_id: Optional[str],
        cancel_token: Optional[OrchestrationCancelToken],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle a finish decision by streaming supervisor summary and final done event."""
        finish_reason = decision.reason or "supervisor_finish"
        async for event in self._stream_supervisor_summary(
            finish_reason=finish_reason,
            current_round=current_round,
            state=state,
            supervisor=supervisor,
            draft_summary=decision.final_response,
            session_id=session_id,
            raw_user_message=raw_user_message,
            group_assistants=group_assistants,
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            supervisor_obj=supervisor_obj,
            assistant_name_map=assistant_name_map,
            reasoning_effort=reasoning_effort,
            context_type=context_type,
            project_id=project_id,
            search_context=search_context,
            search_sources=search_sources,
            trace_id=trace_id,
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
        session_id: str,
        raw_user_message: str,
        group_assistants: List[str],
        supervisor_id: str,
        supervisor_name: str,
        supervisor_obj: Any,
        supervisor: CommitteeSupervisor,
        assistant_name_map: Dict[str, str],
        assistant_config_map: Dict[str, Any],
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[Dict[str, Any]],
        committee_settings: ResolvedCommitteeSettings,
        trace_id: Optional[str],
        cancel_token: Optional[OrchestrationCancelToken],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle parallel_speak by executing selected members concurrently."""
        if self.is_cancelled(cancel_token):
            yield self._build_cancelled_event(state=state, cancel_token=cancel_token)
            return

        parallel_targets = [
            assistant_id
            for assistant_id in (decision.assistant_ids or [])
            if assistant_id in assistant_config_map
        ]
        if len(parallel_targets) < 2:
            fallback_target = decision.assistant_id if decision.assistant_id in assistant_config_map else None
            if not fallback_target and parallel_targets:
                fallback_target = parallel_targets[0]
            if not fallback_target:
                yield {
                    "type": "group_done",
                    "mode": self.mode,
                    "reason": "invalid_parallel_targets",
                    "rounds": state.round_index,
                }
                return
            decision.action = "speak"
            decision.assistant_id = fallback_target
            decision.assistant_ids = None
            async for event in self._handle_speak_action(
                decision=decision,
                current_round=current_round,
                state=state,
                runtime=runtime,
                session_id=session_id,
                raw_user_message=raw_user_message,
                group_assistants=group_assistants,
                supervisor_id=supervisor_id,
                supervisor_name=supervisor_name,
                supervisor_obj=supervisor_obj,
                supervisor=supervisor,
                assistant_name_map=assistant_name_map,
                assistant_config_map=assistant_config_map,
                reasoning_effort=reasoning_effort,
                context_type=context_type,
                project_id=project_id,
                search_context=search_context,
                search_sources=search_sources,
                committee_settings=committee_settings,
                trace_id=trace_id,
                cancel_token=cancel_token,
            ):
                yield event
            return

        event_queue: asyncio.Queue = asyncio.Queue()
        parallel_message_ids: Dict[str, Optional[str]] = {}
        parallel_errors: List[Dict[str, Any]] = []

        async def _run_parallel_target(target_id: str) -> None:
            target_obj = assistant_config_map[target_id]
            target_instruction = decision.instruction
            try:
                turn_packet = self.build_committee_turn_packet(
                    state=state,
                    target_assistant_id=target_id,
                    assistant_name_map=assistant_name_map,
                    instruction=target_instruction,
                )
                async for event in self.stream_group_assistant_turn(
                    session_id=session_id,
                    assistant_id=target_id,
                    assistant_obj=target_obj,
                    group_assistants=group_assistants,
                    assistant_name_map=assistant_name_map,
                    raw_user_message=raw_user_message,
                    reasoning_effort=reasoning_effort,
                    context_type=context_type,
                    project_id=project_id,
                    search_context=search_context,
                    search_sources=search_sources,
                    instruction=target_instruction,
                    committee_turn_packet=turn_packet,
                    trace_id=trace_id,
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
                        "assistant_name": assistant_name_map.get(target_id, target_id),
                        "error": str(e),
                    }
                )
                await event_queue.put(
                    {
                        "kind": "error",
                        "assistant_id": target_id,
                        "assistant_name": assistant_name_map.get(target_id, target_id),
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
                yield self._build_cancelled_event(state=state, cancel_token=cancel_token)
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
                    "supervisor_id": supervisor_id,
                    "supervisor_name": supervisor_name,
                }
            elif kind == "done":
                completed_targets += 1

        await asyncio.gather(*tasks, return_exceptions=True)

        successful_targets = [
            target_id for target_id in parallel_targets if parallel_message_ids.get(target_id)
        ]
        if not successful_targets:
            yield {
                "type": "group_done",
                "mode": self.mode,
                "reason": "parallel_speak_failed",
                "rounds": state.round_index,
            }
            return

        for target_id in successful_targets:
            target_message_id = parallel_message_ids.get(target_id)
            await self._record_turn_from_message(
                state=state,
                session_id=session_id,
                message_id=target_message_id,
                assistant_id=target_id,
                assistant_name=assistant_name_map.get(target_id, target_id),
                context_type=context_type,
                project_id=project_id,
                runtime=runtime,
            )

        if parallel_errors and trace_id:
            self.log_group_trace(
                trace_id,
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
        session_id: str,
        raw_user_message: str,
        group_assistants: List[str],
        supervisor_id: str,
        supervisor_name: str,
        supervisor_obj: Any,
        supervisor: CommitteeSupervisor,
        assistant_name_map: Dict[str, str],
        assistant_config_map: Dict[str, Any],
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[Dict[str, Any]],
        committee_settings: ResolvedCommitteeSettings,
        trace_id: Optional[str],
        cancel_token: Optional[OrchestrationCancelToken],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle standard speak action for a single target assistant."""
        if self.is_cancelled(cancel_token):
            yield self._build_cancelled_event(state=state, cancel_token=cancel_token)
            return

        target_id = decision.assistant_id
        if not target_id:
            yield {
                "type": "group_done",
                "mode": self.mode,
                "reason": "invalid_speak_target",
                "rounds": state.round_index,
            }
            return
        target_obj = assistant_config_map.get(target_id)
        if not target_obj:
            yield {
                "type": "group_done",
                "mode": self.mode,
                "reason": "invalid_speak_target",
                "rounds": state.round_index,
            }
            return

        target_message_id: Optional[str] = None
        content = ""
        role_retry_limit = committee_settings.role_retry_limit
        turn_instruction = decision.instruction
        for attempt in range(role_retry_limit + 1):
            if self.is_cancelled(cancel_token):
                yield self._build_cancelled_event(state=state, cancel_token=cancel_token)
                return

            target_message_id = None
            turn_packet = self.build_committee_turn_packet(
                state=state,
                target_assistant_id=target_id,
                assistant_name_map=assistant_name_map,
                instruction=turn_instruction,
            )
            async for event in self.stream_group_assistant_turn(
                session_id=session_id,
                assistant_id=target_id,
                assistant_obj=target_obj,
                group_assistants=group_assistants,
                assistant_name_map=assistant_name_map,
                raw_user_message=raw_user_message,
                reasoning_effort=reasoning_effort,
                context_type=context_type,
                project_id=project_id,
                search_context=search_context,
                search_sources=search_sources,
                instruction=turn_instruction,
                committee_turn_packet=turn_packet,
                trace_id=trace_id,
                trace_round=current_round,
                trace_mode=self.mode,
            ):
                if event.get("type") == "assistant_message_id":
                    target_message_id = event.get("message_id")
                yield event

            content = await self.get_message_content_by_id(
                session_id=session_id,
                message_id=target_message_id,
                context_type=context_type,
                project_id=project_id,
            )
            drift_reason = self.detect_group_role_drift(
                content=content,
                expected_assistant_id=target_id,
                expected_assistant_name=assistant_name_map.get(target_id, target_id),
                participant_name_map=assistant_name_map,
            )
            if drift_reason and attempt < role_retry_limit:
                turn_instruction = self.build_role_retry_instruction(
                    base_instruction=decision.instruction,
                    expected_assistant_name=assistant_name_map.get(target_id, target_id),
                )
                yield {
                    "type": "group_action",
                    "mode": self.mode,
                    "round": current_round,
                    "action": "role_retry",
                    "assistant_id": target_id,
                    "assistant_name": assistant_name_map.get(target_id, target_id),
                    "reason": drift_reason,
                    "supervisor_id": supervisor_id,
                    "supervisor_name": supervisor_name,
                }
                if trace_id:
                    self.log_group_trace(
                        trace_id,
                        "role_retry",
                        {
                            "round": current_round,
                            "assistant_id": target_id,
                            "assistant_name": assistant_name_map.get(target_id, target_id),
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
                assistant_name=assistant_name_map.get(target_id, target_id),
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
        """Load an assistant message and store a normalized turn record."""
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

    async def _stream_supervisor_summary(
        self,
        *,
        finish_reason: str,
        current_round: int,
        state: CommitteeRuntimeState,
        supervisor: CommitteeSupervisor,
        session_id: str,
        raw_user_message: str,
        group_assistants: List[str],
        supervisor_id: str,
        supervisor_name: str,
        supervisor_obj: Any,
        assistant_name_map: Dict[str, str],
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[Dict[str, Any]],
        trace_id: Optional[str],
        cancel_token: Optional[OrchestrationCancelToken],
        draft_summary: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream final supervisor synthesis and emit canonical group_done event."""
        if self.is_cancelled(cancel_token):
            yield self._build_cancelled_event(state=state, cancel_token=cancel_token)
            return

        summary_instruction = supervisor.build_summary_instruction(
            state,
            reason=finish_reason,
            draft_summary=draft_summary,
        )
        summary_packet = self.build_committee_turn_packet(
            state=state,
            target_assistant_id=supervisor_id,
            assistant_name_map=assistant_name_map,
            instruction=summary_instruction,
        )
        async for event in self.stream_group_assistant_turn(
            session_id=session_id,
            assistant_id=supervisor_id,
            assistant_obj=supervisor_obj,
            group_assistants=group_assistants,
            assistant_name_map=assistant_name_map,
            raw_user_message=raw_user_message,
            reasoning_effort=reasoning_effort,
            context_type=context_type,
            project_id=project_id,
            search_context=search_context,
            search_sources=search_sources,
            instruction=summary_instruction,
            committee_turn_packet=summary_packet,
            trace_id=trace_id,
            trace_round=current_round,
            trace_mode=self.mode,
        ):
            yield event
        if trace_id:
            self.log_group_trace(
                trace_id,
                "committee_done",
                {
                    "reason": finish_reason,
                    "rounds": state.round_index,
                },
            )
        yield {
            "type": "group_done",
            "mode": self.mode,
            "reason": finish_reason,
            "rounds": state.round_index,
        }

    def _build_cancelled_event(
        self,
        *,
        state: CommitteeRuntimeState,
        cancel_token: Optional[OrchestrationCancelToken],
    ) -> Dict[str, Any]:
        reason = "cancelled"
        if cancel_token and isinstance(cancel_token.reason, str):
            cleaned_reason = cancel_token.reason.strip()
            if cleaned_reason:
                reason = cleaned_reason
        return {
            "type": "group_done",
            "mode": self.mode,
            "reason": reason,
            "rounds": state.round_index,
        }
