"""Unified chat orchestration gateway."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Protocol

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
from .service_contracts import SourcePayload, StreamItem


@dataclass(frozen=True)
class _GatewayRuntimeRoute:
    """Resolved runtime route for one chat gateway request."""

    mode: str
    source_factory: Callable[[], AsyncIterator[StreamItem]]


class SingleChatFlowServiceLike(Protocol):
    """Minimal single-chat flow interface consumed by gateway routes."""

    def process_message_stream(
        self,
        *,
        request: SingleChatRequestContext,
    ) -> AsyncIterator[StreamItem]: ...


class CompareFlowServiceLike(Protocol):
    """Minimal compare-chat flow interface consumed by gateway routes."""

    def process_compare_stream(
        self,
        *,
        request: CompareChatRequestContext,
    ) -> AsyncIterator[StreamItem]: ...


class GroupChatFlowServiceLike(Protocol):
    """Minimal group-chat flow interface consumed by gateway routes."""

    def process_group_message_stream(
        self,
        *,
        request: GroupChatRequestContext,
    ) -> AsyncIterator[StreamItem]: ...


@dataclass(frozen=True)
class ChatOrchestrationGatewayDeps:
    """Dependencies required by ChatOrchestrationGateway."""

    single_chat_flow_service: SingleChatFlowServiceLike
    compare_flow_service: CompareFlowServiceLike
    group_chat_service: GroupChatFlowServiceLike
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
    ) -> tuple[str, list[SourcePayload]]:
        """Run one single_direct orchestration request through the runtime and collect output."""
        response_chunks: list[str] = []
        latest_sources: list[SourcePayload] = []

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
    ) -> AsyncIterator[StreamItem]:
        """Stream single_direct mode through the unified gateway."""
        async for event in self._stream_route(
            self._single_route(request),
        ):
            yield event

    async def stream_group(
        self,
        *,
        request: GroupChatRequestContext,
    ) -> AsyncIterator[StreamItem]:
        """Stream round_robin/committee modes through the unified gateway."""
        async for event in self._stream_route(
            self._group_route(request),
        ):
            yield event

    async def stream_compare(
        self,
        *,
        request: CompareChatRequestContext,
    ) -> AsyncIterator[StreamItem]:
        """Stream compare_models mode through the unified gateway."""
        async for event in self._stream_route(
            self._compare_route(request),
        ):
            yield event

    def _single_route(self, request: SingleChatRequestContext) -> _GatewayRuntimeRoute:
        """Build the runtime route for single-message streaming."""
        return _GatewayRuntimeRoute(
            mode="single_direct",
            source_factory=lambda: self._single_chat_flow_service.process_message_stream(
                request=request,
            ),
        )

    @staticmethod
    def _group_mode(request: GroupChatRequestContext) -> str:
        """Normalize one group mode before routing into the runtime."""
        return (request.group_mode or "round_robin").strip().lower()

    def _group_route(self, request: GroupChatRequestContext) -> _GatewayRuntimeRoute:
        """Build the runtime route for group-message streaming."""
        return _GatewayRuntimeRoute(
            mode=self._group_mode(request),
            source_factory=lambda: self._group_chat_service.process_group_message_stream(
                request=request,
            ),
        )

    def _compare_route(self, request: CompareChatRequestContext) -> _GatewayRuntimeRoute:
        """Build the runtime route for compare-message streaming."""
        return _GatewayRuntimeRoute(
            mode="compare_models",
            source_factory=lambda: self._compare_flow_service.process_compare_stream(
                request=request,
            ),
        )

    async def _stream_route(
        self,
        route: _GatewayRuntimeRoute,
    ) -> AsyncIterator[StreamItem]:
        """Stream one resolved route through the orchestration runtime."""
        async for event in self._stream_via_runtime(
            mode=route.mode,
            source_factory=route.source_factory,
        ):
            yield event

    async def _stream_via_runtime(
        self,
        *,
        mode: str,
        source_factory: Callable[[], AsyncIterator[StreamItem]],
    ) -> AsyncIterator[StreamItem]:
        run_id = f"chat-{mode}-{uuid.uuid4().hex}"
        spec = self._build_runtime_spec(
            run_id=run_id,
            mode=mode,
            source_factory=source_factory,
        )
        context = self._build_runtime_context(run_id)
        async for runtime_event in self._orchestration_engine.run_stream(spec, context):
            event_type = str(runtime_event.get("type") or "")
            if event_type == "node_event" and runtime_event.get("event_type") == "chat_event":
                payload = runtime_event.get("payload") or {}
                if isinstance(payload, dict) and "event" in payload:
                    event = payload["event"]
                    if isinstance(event, str) or isinstance(event, dict):
                        yield event
                continue
            if event_type in {"failed", "cancelled"}:
                raise RuntimeError(
                    str(runtime_event.get("terminal_reason") or "chat stream failed")
                )

    def _build_runtime_spec(
        self,
        *,
        run_id: str,
        mode: str,
        source_factory: Callable[[], AsyncIterator[StreamItem]],
    ) -> RunSpec:
        """Build a minimal one-node runtime spec for one chat route."""
        return RunSpec(
            run_id=run_id,
            entry_node_id="chat_adapter",
            nodes=(
                NodeSpec(
                    node_id="chat_adapter",
                    actor=ActorRef(
                        actor_id="chat_adapter",
                        kind=f"chat_{mode}",
                        handler=self._build_adapter_actor(
                            mode=mode,
                            source_factory=source_factory,
                        ),
                    ),
                ),
            ),
            metadata={"mode": mode},
        )

    @staticmethod
    def _build_runtime_context(run_id: str) -> RunContext:
        """Build the isolated runtime context used by gateway adapter runs."""
        return RunContext(
            run_id=run_id,
            max_steps=2,
            context_manager=InMemoryContextManager(),
        )

    @staticmethod
    def _build_adapter_actor(
        *,
        mode: str,
        source_factory: Callable[[], AsyncIterator[StreamItem]],
    ) -> Callable[[ActorExecutionContext], AsyncIterator[ActorEmit | ActorResult]]:
        """Wrap one chat source iterator into an orchestration actor."""

        async def _adapter_actor(_: ActorExecutionContext) -> AsyncIterator[ActorEmit | ActorResult]:
            async for event in source_factory():
                yield ActorEmit(event_type="chat_event", payload={"event": event})
            yield ActorResult(
                terminal_status="completed",
                terminal_reason=f"{mode} completed",
            )

        return _adapter_actor
