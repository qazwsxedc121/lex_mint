"""Unified chat orchestration gateway."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from src.application.orchestration import (
    ActorEmit,
    ActorExecutionContext,
    ActorRef,
    ActorResult,
    InMemoryContextManager,
    NodeSpec,
    OrchestrationEngine,
    RunContext,
    RunSpec,
)

from .request_contexts import (
    CompareChatRequestContext,
    GroupChatRequestContext,
    SingleChatRequestContext,
)


@dataclass(frozen=True)
class ChatOrchestrationGatewayDeps:
    """Dependencies required by ChatOrchestrationGateway."""

    single_chat_flow_service: Any
    compare_flow_service: Any
    group_chat_service: Any
    orchestration_engine: OrchestrationEngine | None = None


class ChatOrchestrationGateway:
    """Single entrypoint for single/group/compare chat orchestration."""

    def __init__(self, deps: ChatOrchestrationGatewayDeps):
        self._single_chat_flow_service = deps.single_chat_flow_service
        self._compare_flow_service = deps.compare_flow_service
        self._group_chat_service = deps.group_chat_service
        self._orchestration_engine = deps.orchestration_engine or OrchestrationEngine()

    async def run_single_message(
        self,
        *,
        request: SingleChatRequestContext,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Run one single_direct orchestration request through the runtime and collect output."""
        response_chunks: list[str] = []
        latest_sources: list[dict[str, Any]] = []

        async for event in self.stream_single(
            request=request,
        ):
            if isinstance(event, str):
                response_chunks.append(event)
                continue
            if isinstance(event, dict) and event.get("type") == "sources":
                sources = event.get("sources")
                if isinstance(sources, list):
                    latest_sources = sources

        return "".join(response_chunks), latest_sources

    async def stream_single(
        self,
        *,
        request: SingleChatRequestContext,
    ) -> AsyncIterator[Any]:
        """Stream single_direct mode through the unified gateway."""
        async for event in self._stream_via_runtime(
            mode="single_direct",
            source_factory=lambda: self._single_chat_flow_service.process_message_stream(
                request=request,
            ),
        ):
            yield event

    async def stream_group(
        self,
        *,
        request: GroupChatRequestContext,
    ) -> AsyncIterator[Any]:
        """Stream round_robin/committee modes through the unified gateway."""
        normalized_mode = (request.group_mode or "round_robin").strip().lower()
        async for event in self._stream_via_runtime(
            mode=normalized_mode,
            source_factory=lambda: self._group_chat_service.process_group_message_stream(
                request=request,
            ),
        ):
            yield event

    async def stream_compare(
        self,
        *,
        request: CompareChatRequestContext,
    ) -> AsyncIterator[Any]:
        """Stream compare_models mode through the unified gateway."""
        async for event in self._stream_via_runtime(
            mode="compare_models",
            source_factory=lambda: self._compare_flow_service.process_compare_stream(
                request=request,
            ),
        ):
            yield event

    async def _stream_via_runtime(
        self,
        *,
        mode: str,
        source_factory: Callable[[], AsyncIterator[Any]],
    ) -> AsyncIterator[Any]:
        run_id = f"chat-{mode}-{uuid.uuid4().hex}"

        async def _adapter_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            async for event in source_factory():
                yield ActorEmit(event_type="chat_event", payload={"event": event})
            yield ActorResult(
                terminal_status="completed",
                terminal_reason=f"{mode} completed",
            )

        spec = RunSpec(
            run_id=run_id,
            entry_node_id="chat_adapter",
            nodes=(
                NodeSpec(
                    node_id="chat_adapter",
                    actor=ActorRef(
                        actor_id="chat_adapter",
                        kind=f"chat_{mode}",
                        handler=_adapter_actor,
                    ),
                ),
            ),
            metadata={"mode": mode},
        )
        context = RunContext(
            run_id=run_id,
            max_steps=2,
            context_manager=InMemoryContextManager(),
        )
        async for runtime_event in self._orchestration_engine.run_stream(spec, context):
            event_type = str(runtime_event.get("type") or "")
            if event_type == "node_event" and runtime_event.get("event_type") == "chat_event":
                payload = runtime_event.get("payload") or {}
                if isinstance(payload, dict) and "event" in payload:
                    yield payload["event"]
                continue
            if event_type in {"failed", "cancelled"}:
                raise RuntimeError(
                    str(runtime_event.get("terminal_reason") or "chat stream failed")
                )
