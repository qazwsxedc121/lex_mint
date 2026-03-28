"""Compare-models orchestrator for multiplexed multi-model streaming."""

from __future__ import annotations

import asyncio
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
from src.providers.types import TokenUsage

from .base import (
    BaseChatOrchestrator,
    ChatOrchestrationCancelToken,
    ChatOrchestrationEvent,
    ChatOrchestrationRequest,
)
from .terminal import build_compare_complete_event, cancellation_reason


@dataclass(frozen=True)
class CompareModelsSettings:
    """Settings for one compare-models orchestration run."""

    messages: list[dict[str, Any]]
    model_ids: list[str]
    system_prompt: str | None
    max_rounds: int | None
    context_segments: dict[str, str | None] = field(default_factory=dict)
    assistant_params: dict[str, Any] = field(default_factory=dict)
    reasoning_effort: str | None = None


class CompareModelsOrchestrator(BaseChatOrchestrator):
    """Runs multiple model streams concurrently and multiplexes events."""

    mode = "compare_models"

    def __init__(
        self,
        *,
        call_llm_stream: Callable[..., AsyncIterator[Any]],
        pricing_service: Any,
        file_service: Any,
        resolve_model_name: Callable[[str], str] | None = None,
        orchestration_engine: OrchestrationEngine | None = None,
    ):
        self.call_llm_stream = call_llm_stream
        self.pricing_service = pricing_service
        self.file_service = file_service
        self.resolve_model_name = resolve_model_name
        self.orchestration_engine = orchestration_engine or OrchestrationEngine()

    async def stream(
        self,
        request: ChatOrchestrationRequest,
        *,
        cancel_token: ChatOrchestrationCancelToken | None = None,
    ) -> AsyncIterator[ChatOrchestrationEvent]:
        if request.mode and request.mode != self.mode:
            raise ValueError(f"CompareModelsOrchestrator only supports mode={self.mode}")
        if not isinstance(request.settings, CompareModelsSettings):
            raise ValueError("CompareModelsOrchestrator requires CompareModelsSettings")

        settings = request.settings
        run_id = f"compare-{request.session_id[:12]}-{uuid.uuid4().hex[:8]}"
        spec = RunSpec(
            run_id=run_id,
            entry_node_id="compare_driver",
            nodes=(
                NodeSpec(
                    node_id="compare_driver",
                    actor=ActorRef(
                        actor_id="compare_driver",
                        kind="compare_models",
                        handler=lambda ctx: self._run_compare_actor(
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

        completion_emitted = False
        async for runtime_event in self.orchestration_engine.run_stream(spec, context):
            event_type = str(runtime_event.get("type") or "")
            if event_type == "node_event" and runtime_event.get("event_type") == "compare_event":
                payload = runtime_event.get("payload") or {}
                if not isinstance(payload, dict):
                    continue
                event = payload.get("event")
                if isinstance(event, dict):
                    normalized = self.normalize_event(event)
                    if normalized.get("type") == "compare_complete":
                        completion_emitted = True
                    yield normalized
                continue
            if event_type in {"failed", "cancelled"} and not completion_emitted:
                reason = str(
                    runtime_event.get("terminal_reason") or cancellation_reason(cancel_token)
                )
                completion_emitted = True
                yield self.normalize_event(
                    build_compare_complete_event(
                        model_results={},
                        reason=reason,
                    )
                )

        if not completion_emitted:
            yield self.normalize_event(
                build_compare_complete_event(
                    model_results={},
                    reason=cancellation_reason(cancel_token),
                )
            )

    async def _run_compare_actor(
        self,
        *,
        execution_context: ActorExecutionContext,
        request: ChatOrchestrationRequest,
        settings: CompareModelsSettings,
        cancel_token: ChatOrchestrationCancelToken | None,
    ) -> AsyncIterator[Any]:
        queue: asyncio.Queue = asyncio.Queue()
        tasks: list[asyncio.Task] = []
        model_results: dict[str, dict[str, Any]] = {}
        finished = 0

        async def _stream_model(model_id: str) -> None:
            model_name = self._resolve_model_name(model_id)
            full_response = ""
            usage_data: TokenUsage | None = None
            cost_data = None
            try:
                await queue.put(
                    {
                        "kind": "event",
                        "event": {
                            "type": "model_start",
                            "model_id": model_id,
                            "model_name": model_name,
                        },
                    }
                )

                async for chunk in self.call_llm_stream(
                    settings.messages,
                    session_id=request.session_id,
                    model_id=model_id,
                    system_prompt=settings.system_prompt,
                    context_segments=settings.context_segments,
                    max_rounds=settings.max_rounds,
                    reasoning_effort=settings.reasoning_effort,
                    file_service=self.file_service,
                    **settings.assistant_params,
                ):
                    if self.is_cancelled(cancel_token):
                        break
                    if isinstance(chunk, dict) and chunk.get("type") == "usage":
                        raw_usage = chunk.get("usage")
                        if isinstance(raw_usage, dict):
                            usage_data = TokenUsage(**raw_usage)
                        elif isinstance(raw_usage, TokenUsage):
                            usage_data = raw_usage
                        if usage_data is not None:
                            parts = model_id.split(":", 1)
                            provider_id = parts[0] if len(parts) > 1 else ""
                            simple_model_id = parts[1] if len(parts) > 1 else model_id
                            cost_data = self.pricing_service.calculate_cost(
                                provider_id, simple_model_id, usage_data
                            )
                        continue

                    if isinstance(chunk, dict):
                        continue

                    text = str(chunk)
                    full_response += text
                    await queue.put(
                        {
                            "kind": "event",
                            "event": {"type": "model_chunk", "model_id": model_id, "chunk": text},
                        }
                    )

                usage_dump = usage_data.model_dump() if usage_data else None
                cost_dump = cost_data.model_dump() if cost_data else None
                if not self.is_cancelled(cancel_token):
                    await queue.put(
                        {
                            "kind": "event",
                            "event": {
                                "type": "model_done",
                                "model_id": model_id,
                                "model_name": model_name,
                                "content": full_response,
                                "usage": usage_dump,
                                "cost": cost_dump,
                            },
                        }
                    )
                model_results[model_id] = {
                    "model_id": model_id,
                    "model_name": model_name,
                    "content": full_response,
                    "usage": usage_dump,
                    "cost": cost_dump,
                    "thinking_content": "",
                    "error": None,
                }
            except Exception as exc:
                await queue.put(
                    {
                        "kind": "event",
                        "event": {
                            "type": "model_error",
                            "model_id": model_id,
                            "model_name": model_name,
                            "error": str(exc),
                        },
                    }
                )
                model_results[model_id] = {
                    "model_id": model_id,
                    "model_name": model_name,
                    "content": "",
                    "usage": None,
                    "cost": None,
                    "thinking_content": "",
                    "error": str(exc),
                }
            finally:
                await queue.put({"kind": "done"})

        for model_id in settings.model_ids:
            tasks.append(asyncio.create_task(_stream_model(model_id)))

        cancelled = False
        try:
            while finished < len(tasks):
                if self.is_cancelled(cancel_token):
                    cancelled = True
                    break
                item = await queue.get()
                if item.get("kind") == "done":
                    finished += 1
                    continue
                event = item.get("event")
                if isinstance(event, dict):
                    yield ActorEmit(event_type="compare_event", payload={"event": event})
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        reason = cancellation_reason(cancel_token) if cancelled else "completed"
        await execution_context.patch_context(
            namespace="compare",
            payload={
                "reason": reason,
                "model_results": model_results,
            },
        )
        yield ActorEmit(
            event_type="compare_event",
            payload={
                "event": build_compare_complete_event(
                    model_results=model_results,
                    reason=reason,
                )
            },
        )
        yield ActorResult(
            terminal_status="completed",
            terminal_reason=reason,
            payload={"reason": reason, "model_results": model_results},
        )

    def _resolve_model_name(self, model_id: str) -> str:
        if self.resolve_model_name is None:
            return model_id
        try:
            return self.resolve_model_name(model_id)
        except Exception:
            return model_id
