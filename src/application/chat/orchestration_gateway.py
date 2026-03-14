"""Unified chat orchestration gateway."""

from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

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


@dataclass(frozen=True)
class ChatOrchestrationGatewayDeps:
    """Dependencies required by ChatOrchestrationGateway."""

    single_chat_flow_service: Any
    compare_flow_service: Any
    group_chat_service: Any
    orchestration_engine: Optional[OrchestrationEngine] = None


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
        session_id: str,
        user_message: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
        active_file_path: Optional[str] = None,
        active_file_hash: Optional[str] = None,
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Run one single_direct orchestration request and collect output."""

        return await self._single_chat_flow_service.process_message(
            session_id=session_id,
            user_message=user_message,
            context_type=context_type,
            project_id=project_id,
            use_web_search=use_web_search,
            search_query=search_query,
            file_references=file_references,
            active_file_path=active_file_path,
            active_file_hash=active_file_hash,
        )

    async def stream_single(
        self,
        *,
        session_id: str,
        user_message: str,
        skip_user_append: bool = False,
        reasoning_effort: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
        active_file_path: Optional[str] = None,
        active_file_hash: Optional[str] = None,
    ) -> AsyncIterator[Any]:
        """Stream single_direct mode through the unified gateway."""
        async for event in self._stream_via_runtime(
            mode="single_direct",
            source_factory=lambda: self._single_chat_flow_service.process_message_stream(
                session_id=session_id,
                user_message=user_message,
                skip_user_append=skip_user_append,
                reasoning_effort=reasoning_effort,
                attachments=attachments,
                context_type=context_type,
                project_id=project_id,
                use_web_search=use_web_search,
                search_query=search_query,
                file_references=file_references,
                active_file_path=active_file_path,
                active_file_hash=active_file_hash,
            ),
        ):
            yield event

    async def stream_group(
        self,
        *,
        session_id: str,
        user_message: str,
        group_assistants: List[str],
        group_mode: str = "round_robin",
        group_settings: Optional[Dict[str, Any]] = None,
        skip_user_append: bool = False,
        reasoning_effort: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[Any]:
        """Stream round_robin/committee modes through the unified gateway."""
        normalized_mode = (group_mode or "round_robin").strip().lower()
        async for event in self._stream_via_runtime(
            mode=normalized_mode,
            source_factory=lambda: self._group_chat_service.process_group_message_stream(
                session_id=session_id,
                user_message=user_message,
                group_assistants=group_assistants,
                group_mode=group_mode,
                group_settings=group_settings,
                skip_user_append=skip_user_append,
                reasoning_effort=reasoning_effort,
                attachments=attachments,
                context_type=context_type,
                project_id=project_id,
                use_web_search=use_web_search,
                search_query=search_query,
                file_references=file_references,
            ),
        ):
            yield event

    async def stream_compare(
        self,
        *,
        session_id: str,
        user_message: str,
        model_ids: List[str],
        reasoning_effort: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[Any]:
        """Stream compare_models mode through the unified gateway."""
        async for event in self._stream_via_runtime(
            mode="compare_models",
            source_factory=lambda: self._compare_flow_service.process_compare_stream(
                session_id=session_id,
                user_message=user_message,
                model_ids=model_ids,
                reasoning_effort=reasoning_effort,
                attachments=attachments,
                context_type=context_type,
                project_id=project_id,
                use_web_search=use_web_search,
                search_query=search_query,
                file_references=file_references,
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
                raise RuntimeError(str(runtime_event.get("terminal_reason") or "chat stream failed"))
