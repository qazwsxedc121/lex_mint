"""Committee orchestration loop."""

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any, Optional, cast

from src.application.chat.request_contexts import CommitteeExecutionContext
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
)
from .committee_actions import CommitteeActionExecutor, CommitteeRunContext
from .committee_loop import CommitteeLoopContext, CommitteeLoopStateMachine
from .committee_types import CommitteeRuntimeConfig, CommitteeRuntimeState
from .runtime import CommitteeRuntime
from .settings import ResolvedCommitteeSettings
from .supervisor import CommitteeSupervisor
from .terminal import build_group_done_event


class CommitteeOrchestrator(BaseChatOrchestrator):
    """Runs committee rounds and emits group events without owning business services."""

    mode = "committee"

    def __init__(
        self,
        *,
        llm_call: Callable[..., str],
        assistant_params_from_config: Callable[[Any], dict[str, Any]],
        stream_group_assistant_turn: Callable[..., AsyncIterator[dict[str, Any]]],
        get_message_content_by_id: Callable[..., Any],
        build_structured_turn_summary: Callable[[str], dict[str, Any]],
        build_committee_turn_packet: Callable[..., dict[str, Any]],
        detect_group_role_drift: Callable[..., str | None],
        build_role_retry_instruction: Callable[..., str],
        truncate_log_text: Callable[[str | None, int], str],
        log_group_trace: Callable[[str, str, dict[str, Any]], None],
        group_trace_preview_chars: int = 1600,
        orchestration_engine: OrchestrationEngine | None = None,
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
        self.orchestration_engine = orchestration_engine or OrchestrationEngine()
        self._loop = CommitteeLoopStateMachine(
            log_group_trace=log_group_trace,
            truncate_log_text=truncate_log_text,
        )
        self._action_executor = CommitteeActionExecutor(
            mode=self.mode,
            stream_group_assistant_turn=stream_group_assistant_turn,
            get_message_content_by_id=get_message_content_by_id,
            build_structured_turn_summary=build_structured_turn_summary,
            build_committee_turn_packet=build_committee_turn_packet,
            detect_group_role_drift=detect_group_role_drift,
            build_role_retry_instruction=build_role_retry_instruction,
            truncate_log_text=truncate_log_text,
            log_group_trace=log_group_trace,
            group_trace_preview_chars=group_trace_preview_chars,
        )

    async def stream(
        self,
        request: ChatOrchestrationRequest,
        *,
        cancel_token: ChatOrchestrationCancelToken | None = None,
    ) -> AsyncIterator[ChatOrchestrationEvent]:
        """Mode-agnostic interface used by orchestrator callers."""
        if request.mode and request.mode != self.mode:
            raise ValueError(f"CommitteeOrchestrator only supports mode={self.mode}")
        if not isinstance(request.settings, ResolvedCommitteeSettings):
            raise ValueError("CommitteeOrchestrator requires ResolvedCommitteeSettings")
        run_id = f"committee-{request.session_id[:12]}-{uuid.uuid4().hex[:8]}"
        spec = RunSpec(
            run_id=run_id,
            entry_node_id="committee_driver",
            nodes=(
                NodeSpec(
                    node_id="committee_driver",
                    actor=ActorRef(
                        actor_id="committee_driver",
                        kind="committee",
                        handler=lambda ctx: self._run_committee_actor(
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
                and runtime_event.get("event_type") == "committee_event"
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
                        reason=str(runtime_event.get("terminal_reason") or "committee_failed"),
                        rounds=0,
                    )
                )
                return

    async def _run_committee_actor(
        self,
        *,
        execution_context: ActorExecutionContext,
        request: ChatOrchestrationRequest,
        cancel_token: ChatOrchestrationCancelToken | None,
    ) -> AsyncIterator[Any]:
        terminated = False
        rounds = 0
        committee_settings = cast(Optional["ResolvedCommitteeSettings"], request.settings)
        if committee_settings is None:
            raise ValueError("Committee orchestrator requires resolved committee settings")
        async for event in self.process(
            execution_context=CommitteeExecutionContext.from_orchestration_request(request),
            committee_settings=committee_settings,
            cancel_token=cancel_token,
        ):
            if event.get("type") == "group_done":
                terminated = True
                rounds = int(event.get("rounds") or 0)
            yield ActorEmit(event_type="committee_event", payload={"event": event})

        await execution_context.patch_context(
            namespace="group",
            payload={"terminated": terminated, "rounds": rounds, "mode": self.mode},
        )
        yield ActorResult(
            terminal_status="completed",
            terminal_reason="completed",
            payload={"rounds": rounds, "terminated": terminated},
        )

    async def process(
        self,
        *,
        execution_context: CommitteeExecutionContext,
        committee_settings: ResolvedCommitteeSettings,
        cancel_token: ChatOrchestrationCancelToken | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Committee mode orchestration: supervisor decides who speaks each round."""
        session_id = execution_context.scope.session_id
        trace_id = execution_context.trace_id
        participant_order = [
            assistant_id
            for assistant_id in execution_context.group_assistants
            if assistant_id in execution_context.assistant_config_map
        ]
        if not participant_order:
            yield build_group_done_event(mode=self.mode, reason="no_valid_participants", rounds=0)
            return

        supervisor_id, supervisor_obj = self._resolve_supervisor(
            participant_order=participant_order,
            assistant_config_map=execution_context.assistant_config_map,
            requested_supervisor_id=committee_settings.supervisor_id,
        )
        supervisor_name = execution_context.assistant_name_map.get(supervisor_id, supervisor_id)
        max_rounds = committee_settings.max_rounds

        self._log_committee_start(
            trace_id=trace_id,
            session_id=session_id,
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            participant_order=participant_order,
            max_rounds=max_rounds,
            committee_settings=committee_settings,
            raw_user_message=execution_context.raw_user_message,
        )

        runtime = CommitteeRuntime(
            CommitteeRuntimeConfig(supervisor_id=supervisor_id, max_rounds=max_rounds)
        )
        state = CommitteeRuntimeState(
            user_message=execution_context.raw_user_message,
            participants={
                assistant_id: execution_context.assistant_name_map.get(assistant_id, assistant_id)
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
        run_context = CommitteeRunContext(
            execution=execution_context,
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            supervisor_obj=supervisor_obj,
            committee_settings=committee_settings,
        )

        supervisor_call_context: dict[str, Any] = {"round": None}

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

        loop_context = CommitteeLoopContext(
            mode=self.mode,
            max_rounds=max_rounds,
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            assistant_name_map=execution_context.assistant_name_map,
            trace_id=trace_id,
        )

        terminated = False
        async for event in self._loop.run(
            runtime=runtime,
            state=state,
            context=loop_context,
            cancel_token=cancel_token,
            decide_round=lambda current_round, current_state: self._decide_round(
                current_round=current_round,
                state=current_state,
                supervisor=supervisor,
                supervisor_call_context=supervisor_call_context,
                call_supervisor=_call_supervisor,
            ),
            execute_action=lambda decision, current_round: self._action_executor.execute(
                decision=decision,
                current_round=current_round,
                state=state,
                runtime=runtime,
                supervisor=supervisor,
                run_context=run_context,
                cancel_token=cancel_token,
            ),
            build_cancelled_event=self._action_executor.build_cancelled_event,
        ):
            if event.get("type") == "group_done":
                terminated = True
            yield event
        if terminated:
            return

        if self._loop.is_cancelled(cancel_token):
            yield self._action_executor.build_cancelled_event(
                state=state,
                cancel_token=cancel_token,
            )
            return

        async for event in self._action_executor.stream_supervisor_summary(
            finish_reason="max_rounds_reached",
            current_round=runtime.current_round(state),
            state=state,
            supervisor=supervisor,
            run_context=run_context,
            cancel_token=cancel_token,
        ):
            yield event

    def _resolve_supervisor(
        self,
        *,
        participant_order: list[str],
        assistant_config_map: dict[str, Any],
        requested_supervisor_id: str,
    ) -> tuple[str, Any]:
        supervisor_id = requested_supervisor_id
        if supervisor_id not in participant_order:
            supervisor_id = participant_order[0]
        supervisor_obj = assistant_config_map.get(supervisor_id)
        if supervisor_obj is None:
            supervisor_id = participant_order[0]
            supervisor_obj = assistant_config_map[supervisor_id]
        return supervisor_id, supervisor_obj

    def _log_committee_start(
        self,
        *,
        trace_id: str | None,
        session_id: str,
        supervisor_id: str,
        supervisor_name: str,
        participant_order: list[str],
        max_rounds: int,
        committee_settings: ResolvedCommitteeSettings,
        raw_user_message: str,
    ) -> None:
        if not trace_id:
            return
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

    async def _decide_round(
        self,
        *,
        current_round: int,
        state: CommitteeRuntimeState,
        supervisor: CommitteeSupervisor,
        supervisor_call_context: dict[str, Any],
        call_supervisor: Callable[[str, str], Any],
    ) -> Any:
        supervisor_call_context["round"] = current_round
        return await supervisor.decide(state, call_supervisor)
