"""Single-direct orchestrator for one assistant stream."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

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
from .terminal import cancellation_reason


@dataclass(frozen=True)
class SingleDirectSettings:
    """Settings for one single-direct orchestration run."""

    messages: list[dict[str, Any]]
    model_id: str
    system_prompt: str | None
    max_rounds: int | None
    context_segments: dict[str, str | None] = field(default_factory=dict)
    assistant_params: dict[str, Any] = field(default_factory=dict)
    reasoning_effort: str | None = None
    tools: list[Any] | None = None
    tool_executor: Any | None = None


class SingleDirectOrchestrator(BaseChatOrchestrator):
    """Runs one direct model stream and emits normalized orchestration events."""

    mode = "single_direct"

    def __init__(
        self,
        *,
        call_llm_stream: Callable[..., AsyncIterator[Any]],
        file_service: Any,
        orchestration_engine: OrchestrationEngine | None = None,
    ):
        self.call_llm_stream = call_llm_stream
        self.file_service = file_service
        self.orchestration_engine = orchestration_engine or OrchestrationEngine()

    async def stream(
        self,
        request: ChatOrchestrationRequest,
        *,
        cancel_token: ChatOrchestrationCancelToken | None = None,
    ) -> AsyncIterator[ChatOrchestrationEvent]:
        if request.mode and request.mode != self.mode:
            raise ValueError(f"SingleDirectOrchestrator only supports mode={self.mode}")
        if not isinstance(request.settings, SingleDirectSettings):
            raise ValueError("SingleDirectOrchestrator requires SingleDirectSettings")

        settings = request.settings
        run_id = f"single-direct-{request.session_id[:12]}-{uuid.uuid4().hex[:8]}"
        spec = RunSpec(
            run_id=run_id,
            entry_node_id="single_direct_driver",
            nodes=(
                NodeSpec(
                    node_id="single_direct_driver",
                    actor=ActorRef(
                        actor_id="single_direct_driver",
                        kind="single_direct",
                        handler=lambda ctx: self._run_single_direct_actor(
                            execution_context=ctx,
                            request=request,
                            settings=settings,
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
                and runtime_event.get("event_type") == "single_direct_event"
            ):
                payload = runtime_event.get("payload") or {}
                event = payload.get("event") if isinstance(payload, dict) else None
                if isinstance(event, dict):
                    yield self.normalize_event(event)
                continue
            if runtime_event.get("type") in {"failed", "cancelled"}:
                raise RuntimeError(
                    str(runtime_event.get("terminal_reason") or cancellation_reason(cancel_token))
                )

    async def _run_single_direct_actor(
        self,
        *,
        execution_context: ActorExecutionContext,
        request: ChatOrchestrationRequest,
        settings: SingleDirectSettings,
        cancel_token: ChatOrchestrationCancelToken | None,
    ) -> AsyncIterator[Any]:
        reason = "completed"
        if self.is_cancelled(cancel_token):
            reason = cancellation_reason(cancel_token)
        else:
            async for chunk in self.call_llm_stream(
                settings.messages,
                session_id=request.session_id,
                model_id=settings.model_id,
                system_prompt=settings.system_prompt,
                context_segments=settings.context_segments,
                max_rounds=settings.max_rounds,
                reasoning_effort=settings.reasoning_effort,
                file_service=self.file_service,
                tools=settings.tools,
                tool_executor=settings.tool_executor,
                **settings.assistant_params,
            ):
                if self.is_cancelled(cancel_token):
                    reason = cancellation_reason(cancel_token)
                    break
                if isinstance(chunk, dict):
                    yield ActorEmit(
                        event_type="single_direct_event",
                        payload={"event": chunk},
                    )
                    continue
                yield ActorEmit(
                    event_type="single_direct_event",
                    payload={"event": {"type": "assistant_chunk", "chunk": str(chunk)}},
                )

        await execution_context.patch_context(
            namespace="single_direct",
            payload={"reason": reason},
        )
        yield ActorResult(
            terminal_status="completed",
            terminal_reason=reason,
            payload={"reason": reason},
        )
