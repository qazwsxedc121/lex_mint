"""Single-chat streaming flow orchestration."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage

from src.application.chat.rag_tool_service import RagToolService
from src.application.chat.request_contexts import (
    SingleChatRequestContext,
    ToolResolutionContext,
)
from src.application.chat.service_contracts import (
    AssistantLike,
    ContextPayload,
    MessagePayload,
    SourcePayload,
    StreamEvent,
    StreamItem,
)
from src.application.chat.source_diagnostics import merge_tool_diagnostics_into_sources
from src.application.orchestration import (
    ActorEmit,
    ActorExecutionContext,
    ActorRef,
    ActorResult,
    EdgeSpec,
    NodeSpec,
    OrchestrationEngine,
    RunContext,
    RunSpec,
)
from src.llm_runtime import estimate_total_tokens
from src.llm_runtime.stream_call_policy import build_stream_kwargs
from src.llm_runtime.stream_input import prepare_stream_input
from src.llm_runtime.streaming_client import _resolve_streaming_runtime
from src.llm_runtime.tool_loop_runner import ToolLoopRunner, ToolLoopState
from src.llm_runtime.tool_loop_runtime import (
    ToolLoopRoundResult,
    bind_tools_for_tool_loop,
    build_tool_loop_state,
    decide_tool_loop_branch,
    execute_tool_loop_round,
    finalize_tool_loop,
    resolve_active_stream_llm,
    stream_tool_loop_round,
)
from src.providers.types import CostInfo, TokenUsage

logger = logging.getLogger(__name__)


def _default_model_service_factory() -> Any:
    from src.infrastructure.config.model_config_service import ModelConfigService

    return ModelConfigService()


def _default_compression_config_service_factory() -> Any:
    from src.infrastructure.compression.compression_config_service import CompressionConfigService

    return CompressionConfigService()


def _default_compression_service_factory(storage: Any) -> Any:
    from src.infrastructure.compression.compression_service import CompressionService

    return CompressionService(storage)


def _default_project_document_tool_service_factory(**kwargs: Any) -> Any:
    from src.infrastructure.projects.project_document_tool_service import ProjectDocumentToolService

    return ProjectDocumentToolService(**kwargs)


def _default_project_knowledge_base_resolver_factory() -> Any:
    from src.infrastructure.projects.project_knowledge_base_resolver import (
        ProjectKnowledgeBaseResolver,
    )

    return ProjectKnowledgeBaseResolver()


def _default_project_tool_policy_resolver_factory() -> Any:
    from src.infrastructure.projects.project_tool_policy_resolver import ProjectToolPolicyResolver

    return ProjectToolPolicyResolver()


def _default_web_tool_service_factory() -> Any:
    from src.infrastructure.web.web_tool_service import WebToolService

    return WebToolService()


def _default_tool_registry_getter() -> Any:
    from src.tools.registry import get_tool_registry

    return get_tool_registry()


def _default_llm_logger_factory() -> Any:
    from src.utils.llm_logger import get_llm_logger

    return get_llm_logger()


@dataclass(frozen=True)
class SingleChatFlowDeps:
    """Dependencies required by SingleChatFlowService."""

    storage: Any
    chat_input_service: Any
    post_turn_service: Any
    call_llm_stream: Callable[..., AsyncIterator[Any]]
    pricing_service: Any
    file_service: Any
    prepare_context: Callable[..., Awaitable[ContextPayload]]
    build_file_context_block: Callable[[list[dict[str, str]] | None], Awaitable[str]]
    model_service_factory: Callable[[], Any] = _default_model_service_factory
    compression_config_service_factory: Callable[[], Any] = (
        _default_compression_config_service_factory
    )
    compression_service_factory: Callable[[Any], Any] = _default_compression_service_factory
    project_document_tool_service_factory: Callable[..., Any] = (
        _default_project_document_tool_service_factory
    )
    project_knowledge_base_resolver_factory: Callable[[], Any] = (
        _default_project_knowledge_base_resolver_factory
    )
    project_tool_policy_resolver_factory: Callable[[], Any] = (
        _default_project_tool_policy_resolver_factory
    )
    web_tool_service_factory: Callable[[], Any] = _default_web_tool_service_factory
    tool_registry_getter: Callable[[], Any] = _default_tool_registry_getter
    llm_logger_factory: Callable[[], Any] = _default_llm_logger_factory


@dataclass
class SingleChatRuntime:
    """Single-turn runtime context resolved before orchestration stream starts."""

    session_id: str
    context_type: str
    project_id: str | None
    raw_user_message: str
    user_message_id: str | None
    messages: list[MessagePayload]
    assistant_id: str | None
    assistant_obj: AssistantLike | None
    model_id: str
    system_prompt: str | None
    context_segments: dict[str, str | None]
    assistant_params: dict[str, Any]
    all_sources: list[SourcePayload]
    max_rounds: int | None
    assistant_memory_enabled: bool
    active_file_path: str | None = None
    active_file_hash: str | None = None
    compression_event: StreamEvent | None = None


@dataclass
class SingleTurnOutcome:
    """Collected outputs from one single-turn orchestration stream."""

    full_response: str = ""
    usage_data: TokenUsage | None = None
    cost_data: CostInfo | None = None
    tool_diagnostics: SourcePayload | None = None


@dataclass
class SingleChatToolLoopRuntime:
    """Mutable tool-loop runtime state for one single-chat turn."""

    streaming_runtime: Any
    llm_for_tools: Any
    tool_loop_runner: ToolLoopRunner
    tool_loop_state: ToolLoopState
    prompt_messages: list[Any]
    context_info_event: StreamEvent
    tools_enabled: bool
    final_usage: TokenUsage | None = None
    full_reasoning: str = ""
    round_content: str = ""
    round_reasoning: str = ""
    round_reasoning_details: Any = None
    merged_chunk: Any = None
    pending_tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SingleChatExecutionState:
    """Cross-node mutable execution state for one single-chat orchestration run."""

    runtime: SingleChatRuntime | None = None
    llm_tools: list[Any] | None = None
    rag_tool_executor: Any | None = None
    tool_loop: SingleChatToolLoopRuntime | None = None
    outcome: SingleTurnOutcome = field(default_factory=SingleTurnOutcome)


@dataclass
class SingleChatResolvedTools:
    """Resolved tool set and execution policy for one single-chat turn."""

    llm_tools: list[Any] = field(default_factory=list)
    tool_executors: list[Any] = field(default_factory=list)
    allowed_tool_names: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class SingleChatPreparedInput:
    """Prepared user input after optional file-context expansion."""

    raw_user_message: str
    user_message_id: str | None


@dataclass(frozen=True)
class SingleChatPreparedContext:
    """Prepared context payload after optional web-context pruning and compression."""

    messages: list[MessagePayload]
    model_id: str
    system_prompt: str | None
    context_segments: dict[str, str | None]
    all_sources: list[SourcePayload]
    assistant_id: str | None
    assistant_obj: AssistantLike | None
    assistant_params: dict[str, Any]
    max_rounds: int | None
    assistant_memory_enabled: bool
    compression_event: StreamEvent | None


class SingleChatFlowService:
    """Runs single-chat stream flow and emits chat stream events."""

    def __init__(self, deps: SingleChatFlowDeps):
        self.deps = deps
        self._orchestration_engine = OrchestrationEngine()

    async def process_message(
        self,
        *,
        request: SingleChatRequestContext,
    ) -> tuple[str, list[SourcePayload]]:
        """Collect the single-chat stream into one final response payload."""
        response_chunks: list[str] = []
        latest_sources: list[SourcePayload] = []

        async for event in self.process_message_stream(
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

    async def process_message_stream(
        self,
        *,
        request: SingleChatRequestContext,
    ) -> AsyncIterator[StreamItem]:
        """Prepare context, run single-turn orchestration, and persist final outputs."""
        execution_state = SingleChatExecutionState()
        run_id = f"single-chat-{request.scope.session_id[:12]}-{uuid.uuid4().hex[:8]}"
        actor_handlers = self._build_actor_handlers(
            request=request,
            execution_state=execution_state,
        )
        spec = self._build_single_chat_run_spec(
            request=request,
            run_id=run_id,
            actor_handlers=actor_handlers,
        )
        context = self._build_single_chat_run_context(run_id=run_id)

        async for event in self._stream_single_chat_run(spec=spec, context=context):
            yield event

    def _build_actor_handlers(
        self,
        *,
        request: SingleChatRequestContext,
        execution_state: SingleChatExecutionState,
    ) -> dict[str, Callable[[ActorExecutionContext], AsyncIterator[Any]]]:
        """Build one-node handlers for the single-chat orchestration graph."""

        async def _prepare_runtime_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = await self._prepare_runtime(request=request)
            execution_state.runtime = runtime

            if runtime.user_message_id:
                yield self._emit_single_chat_event(
                    {
                        "type": "user_message_id",
                        "message_id": runtime.user_message_id,
                    }
                )
            else:
                print("[Step 1] Skipping user message save (regeneration mode)")
                logger.info("[Step 1] Skipping user message save")

            if runtime.all_sources:
                yield self._emit_single_chat_event(
                    {
                        "type": "sources",
                        "sources": runtime.all_sources,
                    }
                )
            if runtime.compression_event:
                yield self._emit_single_chat_event(runtime.compression_event)
            yield ActorResult()

        async def _resolve_tools_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = self._require_runtime_state(execution_state)
            tool_request = ToolResolutionContext(
                scope=request.scope,
                editor=request.editor,
                assistant_id=runtime.assistant_id,
                assistant_obj=runtime.assistant_obj,
                model_id=runtime.model_id,
                use_web_search=request.search.use_web_search,
            )
            llm_tools, rag_tool_executor = await self._resolve_tools(
                request=tool_request,
            )
            execution_state.llm_tools = llm_tools
            execution_state.rag_tool_executor = rag_tool_executor
            yield ActorResult()

        async def _prepare_tool_loop_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = self._require_runtime_state(execution_state)
            tool_loop = await self._prepare_tool_loop_runtime(
                runtime=runtime,
                reasoning_effort=request.stream.reasoning_effort,
                llm_tools=execution_state.llm_tools,
            )
            execution_state.tool_loop = tool_loop
            yield self._emit_single_chat_event(tool_loop.context_info_event)
            yield ActorResult()

        async def _stream_tool_round_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = self._require_runtime_state(execution_state)
            outcome = self._require_outcome_state(execution_state)
            tool_loop = self._require_tool_loop_state(execution_state)
            async for event in self._stream_tool_loop_round(
                runtime=runtime,
                tool_loop=tool_loop,
                outcome=outcome,
            ):
                yield self._emit_single_chat_event(event)
            yield ActorResult()

        async def _decide_tool_round_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            outcome = self._require_outcome_state(execution_state)
            tool_loop = self._require_tool_loop_state(execution_state)
            branch = self._decide_tool_loop_branch(
                tool_loop=tool_loop,
                outcome=outcome,
            )
            yield ActorResult(branch=branch)

        async def _execute_tools_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            tool_loop = self._require_tool_loop_state(execution_state)
            async for event in self._execute_tool_loop_round(
                tool_loop=tool_loop,
                tool_executor=execution_state.rag_tool_executor,
            ):
                yield self._emit_single_chat_event(event)
            yield ActorResult()

        async def _finalize_tool_loop_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = self._require_runtime_state(execution_state)
            outcome = self._require_outcome_state(execution_state)
            tool_loop = self._require_tool_loop_state(execution_state)
            async for event in self._finalize_tool_loop(
                runtime=runtime,
                outcome=outcome,
                tool_loop=tool_loop,
            ):
                yield self._emit_single_chat_event(event)
            yield ActorResult()

        async def _persist_result_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = self._require_runtime_state(execution_state)
            outcome = self._require_outcome_state(execution_state)
            async for event in self._persist_and_emit(runtime=runtime, outcome=outcome):
                yield self._emit_single_chat_event(event)
            yield ActorResult(terminal_status="completed", terminal_reason="completed")

        return {
            "prepare_runtime": _prepare_runtime_actor,
            "resolve_tools": _resolve_tools_actor,
            "prepare_tool_loop": _prepare_tool_loop_actor,
            "stream_tool_round": _stream_tool_round_actor,
            "decide_tool_round": _decide_tool_round_actor,
            "execute_tools": _execute_tools_actor,
            "finalize_tool_loop": _finalize_tool_loop_actor,
            "persist_result": _persist_result_actor,
        }

    @staticmethod
    def _build_single_chat_run_context(*, run_id: str) -> RunContext:
        """Build the orchestration runtime context for one single-chat run."""
        return RunContext(run_id=run_id, max_steps=24)

    def _build_single_chat_run_spec(
        self,
        *,
        request: SingleChatRequestContext,
        run_id: str,
        actor_handlers: dict[str, Callable[[ActorExecutionContext], AsyncIterator[Any]]],
    ) -> RunSpec:
        """Build the static single-chat orchestration graph."""
        return RunSpec(
            run_id=run_id,
            entry_node_id="prepare_runtime",
            nodes=(
                self._build_single_chat_node(
                    node_id="prepare_runtime",
                    kind="single_chat_prepare",
                    handler=actor_handlers["prepare_runtime"],
                ),
                self._build_single_chat_node(
                    node_id="resolve_tools",
                    kind="single_chat_tools",
                    handler=actor_handlers["resolve_tools"],
                ),
                self._build_single_chat_node(
                    node_id="prepare_tool_loop",
                    kind="single_chat_tool_loop_prepare",
                    handler=actor_handlers["prepare_tool_loop"],
                ),
                self._build_single_chat_node(
                    node_id="stream_tool_round",
                    kind="single_chat_tool_loop_stream",
                    handler=actor_handlers["stream_tool_round"],
                ),
                self._build_single_chat_node(
                    node_id="decide_tool_round",
                    kind="single_chat_tool_loop_branch",
                    handler=actor_handlers["decide_tool_round"],
                ),
                self._build_single_chat_node(
                    node_id="execute_tools",
                    kind="single_chat_tool_loop_execute",
                    handler=actor_handlers["execute_tools"],
                ),
                self._build_single_chat_node(
                    node_id="finalize_tool_loop",
                    kind="single_chat_tool_loop_finalize",
                    handler=actor_handlers["finalize_tool_loop"],
                ),
                self._build_single_chat_node(
                    node_id="persist_result",
                    kind="single_chat_persist",
                    handler=actor_handlers["persist_result"],
                ),
            ),
            edges=self._single_chat_run_edges(),
            metadata={"mode": "single_direct", "session_id": request.scope.session_id},
        )

    @staticmethod
    def _build_single_chat_node(
        *,
        node_id: str,
        kind: str,
        handler: Callable[[ActorExecutionContext], AsyncIterator[Any]],
    ) -> NodeSpec:
        """Build one single-chat graph node from a handler."""
        return NodeSpec(
            node_id=node_id,
            actor=ActorRef(
                actor_id=node_id,
                kind=kind,
                handler=handler,
            ),
        )

    @staticmethod
    def _single_chat_run_edges() -> tuple[EdgeSpec, ...]:
        """Return the static edge set for one single-chat orchestration run."""
        return (
            EdgeSpec(source_id="prepare_runtime", target_id="resolve_tools"),
            EdgeSpec(source_id="resolve_tools", target_id="prepare_tool_loop"),
            EdgeSpec(source_id="prepare_tool_loop", target_id="stream_tool_round"),
            EdgeSpec(source_id="stream_tool_round", target_id="decide_tool_round"),
            EdgeSpec(
                source_id="decide_tool_round", target_id="execute_tools", branch="execute_tools"
            ),
            EdgeSpec(
                source_id="decide_tool_round", target_id="stream_tool_round", branch="continue"
            ),
            EdgeSpec(
                source_id="decide_tool_round", target_id="finalize_tool_loop", branch="finalize"
            ),
            EdgeSpec(source_id="execute_tools", target_id="stream_tool_round"),
            EdgeSpec(source_id="finalize_tool_loop", target_id="persist_result"),
        )

    async def _stream_single_chat_run(
        self,
        *,
        spec: RunSpec,
        context: RunContext,
    ) -> AsyncIterator[StreamItem]:
        """Run the single-chat graph and unwrap emitted chat events."""
        async for runtime_event in self._orchestration_engine.run_stream(spec, context):
            event_type = str(runtime_event.get("type") or "")
            if (
                event_type == "node_event"
                and runtime_event.get("event_type") == "single_chat_event"
            ):
                payload = runtime_event.get("payload") or {}
                if isinstance(payload, dict) and "event" in payload:
                    yield payload["event"]
                continue
            if event_type in {"failed", "cancelled"}:
                raise RuntimeError(
                    str(runtime_event.get("terminal_reason") or "single chat stream failed")
                )

    @staticmethod
    def _emit_single_chat_event(event: StreamItem) -> ActorEmit:
        return ActorEmit(event_type="single_chat_event", payload={"event": event})

    @staticmethod
    def _require_runtime_state(execution_state: SingleChatExecutionState) -> SingleChatRuntime:
        runtime = execution_state.runtime
        if not isinstance(runtime, SingleChatRuntime):
            raise RuntimeError("single chat runtime was not prepared before node execution")
        return runtime

    @staticmethod
    def _require_outcome_state(execution_state: SingleChatExecutionState) -> SingleTurnOutcome:
        outcome = execution_state.outcome
        if not isinstance(outcome, SingleTurnOutcome):
            raise RuntimeError("single chat outcome state is unavailable")
        return outcome

    @staticmethod
    def _require_tool_loop_state(
        execution_state: SingleChatExecutionState,
    ) -> SingleChatToolLoopRuntime:
        tool_loop = execution_state.tool_loop
        if not isinstance(tool_loop, SingleChatToolLoopRuntime):
            raise RuntimeError("single chat tool loop state is unavailable")
        return tool_loop

    async def _prepare_runtime(
        self,
        *,
        request: SingleChatRequestContext,
    ) -> SingleChatRuntime:
        prepared_input = await self._prepare_single_chat_input(request=request)
        prepared_context = await self._prepare_single_chat_context(
            request=request,
            raw_user_message=prepared_input.raw_user_message,
        )

        return SingleChatRuntime(
            session_id=request.scope.session_id,
            context_type=request.scope.context_type,
            project_id=request.scope.project_id,
            raw_user_message=prepared_input.raw_user_message,
            user_message_id=prepared_input.user_message_id,
            messages=prepared_context.messages,
            assistant_id=prepared_context.assistant_id,
            assistant_obj=prepared_context.assistant_obj,
            model_id=prepared_context.model_id,
            system_prompt=prepared_context.system_prompt,
            context_segments=prepared_context.context_segments,
            assistant_params=prepared_context.assistant_params,
            all_sources=prepared_context.all_sources,
            max_rounds=prepared_context.max_rounds,
            assistant_memory_enabled=prepared_context.assistant_memory_enabled,
            active_file_path=(request.editor.active_file_path or "").strip() or None,
            active_file_hash=(request.editor.active_file_hash or "").strip() or None,
            compression_event=prepared_context.compression_event,
        )

    async def _prepare_single_chat_input(
        self,
        *,
        request: SingleChatRequestContext,
    ) -> SingleChatPreparedInput:
        user_message = request.user_input.user_message
        expanded_user_message = await self._expand_user_message_with_file_context(
            user_message=user_message,
            file_references=request.user_input.file_references,
        )
        prepared_input = await self.deps.chat_input_service.prepare_user_input(
            session_id=request.scope.session_id,
            raw_user_message=user_message,
            expanded_user_message=expanded_user_message,
            attachments=request.user_input.attachments,
            skip_user_append=request.stream.skip_user_append,
            context_type=request.scope.context_type,
            project_id=request.scope.project_id,
        )
        return SingleChatPreparedInput(
            raw_user_message=prepared_input.raw_user_message,
            user_message_id=prepared_input.user_message_id,
        )

    async def _expand_user_message_with_file_context(
        self,
        *,
        user_message: str,
        file_references: list[dict[str, str]] | None,
    ) -> str:
        file_context_block = await self.deps.build_file_context_block(file_references)
        if not file_context_block:
            return user_message
        return f"{file_context_block}\n\n{user_message}"

    async def _prepare_single_chat_context(
        self,
        *,
        request: SingleChatRequestContext,
        raw_user_message: str,
    ) -> SingleChatPreparedContext:
        print("[Step 2] Loading session state...")
        logger.info("[Step 2] Loading session state")
        prefer_web_tools = await self._should_prefer_web_tools(
            session_id=request.scope.session_id,
            context_type=request.scope.context_type,
            project_id=request.scope.project_id,
            use_web_search=request.search.use_web_search,
        )
        ctx = await self.deps.prepare_context(
            session_id=request.scope.session_id,
            raw_user_message=raw_user_message,
            context_type=request.scope.context_type,
            project_id=request.scope.project_id,
            use_web_search=request.search.use_web_search and not prefer_web_tools,
            search_query=request.search.search_query,
        )
        print(f"[OK] Session loaded, {len(ctx.messages)} messages")
        print(f"   Assistant: {ctx.assistant_id}, Model: {ctx.model_id}")

        messages, compression_event = await self._maybe_auto_compress(
            session_id=request.scope.session_id,
            model_id=ctx.model_id,
            messages=ctx.messages,
            context_type=request.scope.context_type,
            project_id=request.scope.project_id,
        )
        system_prompt, context_segments, all_sources = self._normalize_context_payload(
            context_payload=ctx,
            prefer_web_tools=prefer_web_tools,
        )
        return SingleChatPreparedContext(
            messages=messages,
            model_id=ctx.model_id,
            system_prompt=system_prompt,
            context_segments=context_segments,
            all_sources=all_sources,
            assistant_id=ctx.assistant_id,
            assistant_obj=ctx.assistant_obj,
            assistant_params=ctx.assistant_params,
            max_rounds=ctx.max_rounds,
            assistant_memory_enabled=ctx.assistant_memory_enabled,
            compression_event=compression_event,
        )

    def _normalize_context_payload(
        self,
        *,
        context_payload: ContextPayload,
        prefer_web_tools: bool,
    ) -> tuple[str | None, dict[str, str | None], list[SourcePayload]]:
        system_prompt = context_payload.system_prompt
        context_segments = {
            "base_system_prompt": context_payload.base_system_prompt,
            "memory_context": context_payload.memory_context,
            "webpage_context": context_payload.webpage_context,
            "search_context": context_payload.search_context,
            "rag_context": context_payload.rag_context,
            "structured_source_context": context_payload.structured_source_context,
        }
        all_sources = list(context_payload.all_sources)
        if prefer_web_tools:
            system_prompt, context_segments, all_sources = self._strip_preloaded_web_context(
                context_segments=context_segments,
                all_sources=all_sources,
            )
        return system_prompt, context_segments, all_sources

    @staticmethod
    def _compose_system_prompt(*segments: str | None) -> str | None:
        parts = [
            str(segment).strip()
            for segment in segments
            if isinstance(segment, str) and segment.strip()
        ]
        return "\n\n".join(parts) if parts else None

    def _strip_preloaded_web_context(
        self,
        *,
        context_segments: dict[str, str | None],
        all_sources: list[SourcePayload],
    ) -> tuple[str | None, dict[str, str | None], list[SourcePayload]]:
        pruned_segments = dict(context_segments)
        pruned_segments["webpage_context"] = None
        pruned_segments["search_context"] = None
        system_prompt = self._compose_system_prompt(
            pruned_segments.get("base_system_prompt"),
            pruned_segments.get("memory_context"),
            pruned_segments.get("rag_context"),
            pruned_segments.get("structured_source_context"),
        )
        filtered_sources = [
            source for source in all_sources if source.get("type") not in {"search", "webpage"}
        ]
        return system_prompt, pruned_segments, filtered_sources

    async def _should_prefer_web_tools(
        self,
        *,
        session_id: str,
        context_type: str,
        project_id: str | None,
        use_web_search: bool,
    ) -> bool:
        if not use_web_search:
            return False

        try:
            session = await self.deps.storage.get_session(
                session_id,
                context_type=context_type,
                project_id=project_id,
            )
            model_id = session.get("model_id")
            param_overrides = session.get("param_overrides", {}) or {}
            if "model_id" in param_overrides:
                model_id = param_overrides["model_id"]
            if not model_id:
                return False

            model_service = self.deps.model_service_factory()
            model_cfg, provider_cfg = model_service.get_model_and_provider_sync(str(model_id))
            merged_caps = model_service.get_merged_capabilities(model_cfg, provider_cfg)
            return bool(getattr(merged_caps, "function_calling", False))
        except Exception as exc:
            logger.warning("Failed to determine web tool preference: %s", exc)
            return False

    async def _stream_single_turn(
        self,
        *,
        runtime: SingleChatRuntime,
        reasoning_effort: str | None,
        llm_tools: list[Any] | None,
        rag_tool_executor: Any | None,
        outcome: SingleTurnOutcome,
    ) -> AsyncIterator[StreamItem]:
        print("[Step 3] Streaming LLM call...")
        logger.info("[Step 3] Streaming LLM call")

        try:
            async for chunk in self.deps.call_llm_stream(
                runtime.messages,
                session_id=runtime.session_id,
                model_id=runtime.model_id,
                system_prompt=runtime.system_prompt,
                context_segments=runtime.context_segments,
                max_rounds=runtime.max_rounds,
                reasoning_effort=reasoning_effort,
                file_service=self.deps.file_service,
                tools=llm_tools,
                tool_executor=rag_tool_executor,
                **runtime.assistant_params,
            ):
                if isinstance(chunk, dict):
                    chunk_type = chunk.get("type")
                    if chunk_type == "usage":
                        usage_data = chunk.get("usage")
                        if isinstance(usage_data, dict):
                            usage_data = TokenUsage(**usage_data)
                        self._apply_usage_to_outcome(
                            runtime=runtime,
                            outcome=outcome,
                            usage_data=usage_data,
                        )
                        continue
                    if chunk_type in (
                        "context_info",
                        "thinking_duration",
                        "tool_calls",
                        "tool_results",
                    ):
                        yield chunk
                        continue
                    if chunk_type == "tool_diagnostics":
                        outcome.tool_diagnostics = dict(chunk)
                        continue

                text_chunk = str(chunk)
                outcome.full_response += text_chunk
                yield text_chunk
            print("[OK] LLM streaming complete")
            logger.info("[OK] LLM streaming complete")
            print(f"[MSG] AI response length: {len(outcome.full_response)} chars")
        except asyncio.CancelledError:
            print("[WARN] Stream generation cancelled, saving partial content...")
            logger.warning(
                "Stream generation cancelled, saving partial content (%s chars)",
                len(outcome.full_response),
            )
            await self.deps.post_turn_service.save_partial_assistant_message(
                session_id=runtime.session_id,
                assistant_message=outcome.full_response,
                context_type=runtime.context_type,
                project_id=runtime.project_id,
            )
            if outcome.full_response:
                print("[OK] Partial AI response saved")
            raise

    async def _prepare_tool_loop_runtime(
        self,
        *,
        runtime: SingleChatRuntime,
        reasoning_effort: str | None,
        llm_tools: list[Any] | None,
    ) -> SingleChatToolLoopRuntime:
        assistant_params = runtime.assistant_params or {}
        streaming_runtime = _resolve_streaming_runtime(
            model_id=runtime.model_id,
            session_id=runtime.session_id,
            temperature=assistant_params.get("temperature"),
            max_tokens=assistant_params.get("max_tokens"),
            top_p=assistant_params.get("top_p"),
            top_k=assistant_params.get("top_k"),
            frequency_penalty=assistant_params.get("frequency_penalty"),
            presence_penalty=assistant_params.get("presence_penalty"),
            reasoning_effort=reasoning_effort,
            model_service_factory=self.deps.model_service_factory,
            llm_logger_factory=self.deps.llm_logger_factory,
        )
        prepared_input = await prepare_stream_input(
            runtime=streaming_runtime,
            messages=runtime.messages,
            session_id=runtime.session_id,
            system_prompt=runtime.system_prompt,
            context_segments=runtime.context_segments,
            max_rounds=runtime.max_rounds,
            file_service=self.deps.file_service,
        )

        latest_user_text = ""
        for raw_message in reversed(runtime.messages):
            if str(raw_message.get("role", "")).strip().lower() == "user":
                latest_user_text = str(raw_message.get("content") or "")
                break

        bound_tools = bind_tools_for_tool_loop(
            llm=streaming_runtime.llm,
            llm_tools=llm_tools,
            warning_message="Failed to bind tools for single-chat tool loop",
        )
        tool_loop_runner, tool_loop_state = build_tool_loop_state(
            langchain_messages=list(prepared_input.langchain_messages),
            latest_user_text=latest_user_text,
            tool_names=bound_tools.tool_names,
        )

        return SingleChatToolLoopRuntime(
            streaming_runtime=streaming_runtime,
            llm_for_tools=bound_tools.llm_for_tools,
            tool_loop_runner=tool_loop_runner,
            tool_loop_state=tool_loop_state,
            prompt_messages=list(prepared_input.langchain_messages),
            context_info_event=prepared_input.context_event,
            tools_enabled=bound_tools.tools_enabled,
        )

    async def _stream_tool_loop_round(
        self,
        *,
        runtime: SingleChatRuntime,
        tool_loop: SingleChatToolLoopRuntime,
        outcome: SingleTurnOutcome,
    ) -> AsyncIterator[StreamItem]:
        print("[Step 3] Streaming tool-aware LLM round...")
        logger.info("Streaming single-chat tool-aware LLM round")

        try:
            active_llm = resolve_active_stream_llm(
                runtime=tool_loop.streaming_runtime,
                llm_for_tools=tool_loop.llm_for_tools,
                tools_enabled=tool_loop.tools_enabled,
                tool_loop_state=tool_loop.tool_loop_state,
            )
            tool_loop.round_content = ""
            tool_loop.round_reasoning = ""
            tool_loop.round_reasoning_details = None
            tool_loop.merged_chunk = None
            tool_loop.pending_tool_calls = []

            round_result: ToolLoopRoundResult | None = None
            async for chunk in stream_tool_loop_round(
                runtime=tool_loop.streaming_runtime,
                active_llm=active_llm,
                current_messages=tool_loop.tool_loop_state.current_messages,
                stream_kwargs=build_stream_kwargs(
                    allow_responses_fallback=tool_loop.streaming_runtime.allow_responses_fallback,
                ),
            ):
                if isinstance(chunk, ToolLoopRoundResult):
                    round_result = chunk
                    continue
                yield chunk

            if round_result is None:
                round_result = ToolLoopRoundResult("", "", None, tool_loop.final_usage, None)
            if round_result.final_usage is not None:
                tool_loop.final_usage = round_result.final_usage
            tool_loop.round_content = round_result.round_content
            tool_loop.round_reasoning = round_result.round_reasoning
            tool_loop.round_reasoning_details = round_result.round_reasoning_details
            tool_loop.merged_chunk = round_result.merged_chunk
            if round_result.round_reasoning:
                tool_loop.full_reasoning += round_result.round_reasoning
            outcome.full_response += round_result.round_content
        except asyncio.CancelledError:
            print("[WARN] Stream generation cancelled, saving partial content...")
            logger.warning(
                "Tool-loop stream generation cancelled, saving partial content (%s chars)",
                len(outcome.full_response),
            )
            await self.deps.post_turn_service.save_partial_assistant_message(
                session_id=runtime.session_id,
                assistant_message=outcome.full_response,
                context_type=runtime.context_type,
                project_id=runtime.project_id,
            )
            raise

    def _decide_tool_loop_branch(
        self,
        *,
        tool_loop: SingleChatToolLoopRuntime,
        outcome: SingleTurnOutcome,
    ) -> str:
        decision = decide_tool_loop_branch(
            tool_loop_runner=tool_loop.tool_loop_runner,
            tool_loop_state=tool_loop.tool_loop_state,
            round_result=ToolLoopRoundResult(
                round_content=tool_loop.round_content,
                round_reasoning=tool_loop.round_reasoning,
                round_reasoning_details=tool_loop.round_reasoning_details,
                final_usage=tool_loop.final_usage,
                merged_chunk=tool_loop.merged_chunk,
            ),
            full_response=outcome.full_response,
            tools_enabled=tool_loop.tools_enabled,
        )
        outcome.full_response = decision.full_response
        tool_loop.pending_tool_calls = decision.round_tool_calls
        if (
            decision.branch == "continue"
            and tool_loop.tool_loop_state.force_finalize_without_tools
        ):
            logger.info("Single-chat tool loop entered force-finalize mode")
        return decision.branch

    async def _execute_tool_loop_round(
        self,
        *,
        tool_loop: SingleChatToolLoopRuntime,
        tool_executor: Any | None,
    ) -> AsyncIterator[StreamEvent]:
        round_tool_calls = list(tool_loop.pending_tool_calls)
        if not round_tool_calls:
            return

        logger.info(
            "Tool call round %s: %s",
            tool_loop.tool_loop_state.tool_round,
            [tool_call["name"] for tool_call in round_tool_calls],
        )
        yield tool_loop.tool_loop_runner.build_tool_calls_event(round_tool_calls)

        tool_results = await execute_tool_loop_round(
            tool_loop_runner=tool_loop.tool_loop_runner,
            tool_loop_state=tool_loop.tool_loop_state,
            round_tool_calls=round_tool_calls,
            tool_executor=tool_executor,
            round_content=tool_loop.round_content,
            round_reasoning=tool_loop.round_reasoning,
            round_reasoning_details=tool_loop.round_reasoning_details,
        )
        yield tool_loop.tool_loop_runner.build_tool_results_event(tool_results)
        tool_loop.pending_tool_calls = []

    async def _finalize_tool_loop(
        self,
        *,
        runtime: SingleChatRuntime,
        outcome: SingleTurnOutcome,
        tool_loop: SingleChatToolLoopRuntime,
    ) -> AsyncIterator[StreamItem]:
        finalize_result = finalize_tool_loop(
            tool_loop_runner=tool_loop.tool_loop_runner,
            tool_loop_state=tool_loop.tool_loop_state,
            full_response=outcome.full_response,
        )
        outcome.full_response = finalize_result.full_response
        if finalize_result.injected_text:
            yield finalize_result.injected_text
        outcome.tool_diagnostics = finalize_result.diagnostics_event
        self._apply_usage_to_outcome(
            runtime=runtime,
            outcome=outcome,
            usage_data=tool_loop.final_usage,
        )
        self._log_tool_loop_interaction(
            runtime=runtime,
            outcome=outcome,
            tool_loop=tool_loop,
        )

    def _apply_usage_to_outcome(
        self,
        *,
        runtime: SingleChatRuntime,
        outcome: SingleTurnOutcome,
        usage_data: TokenUsage | None,
    ) -> None:
        if not isinstance(usage_data, TokenUsage):
            return

        outcome.usage_data = usage_data
        model_parts = runtime.model_id.split(":", 1)
        provider_id = model_parts[0] if len(model_parts) > 1 else ""
        simple_model_id = model_parts[1] if len(model_parts) > 1 else runtime.model_id
        outcome.cost_data = self.deps.pricing_service.calculate_cost(
            provider_id,
            simple_model_id,
            usage_data,
        )

    def _log_tool_loop_interaction(
        self,
        *,
        runtime: SingleChatRuntime,
        outcome: SingleTurnOutcome,
        tool_loop: SingleChatToolLoopRuntime,
    ) -> None:
        response_msg = AIMessage(content=outcome.full_response)
        log_extra_params: dict[str, Any] = {
            "request_params": tool_loop.streaming_runtime.request_params,
            "call_mode": tool_loop.streaming_runtime.effective_call_mode.value,
            "responses_fallback_enabled": tool_loop.streaming_runtime.allow_responses_fallback,
            "tool_finalize_reason": tool_loop.tool_loop_state.tool_finalize_reason,
        }
        reasoning_decision = tool_loop.streaming_runtime.reasoning_decision
        if reasoning_decision.disable_thinking:
            log_extra_params["thinking_enabled"] = False
            log_extra_params["reasoning_mode"] = "none"
        elif reasoning_decision.thinking_enabled:
            log_extra_params["thinking_enabled"] = True
            if reasoning_decision.effective_reasoning_option:
                log_extra_params["reasoning_option"] = reasoning_decision.effective_reasoning_option
            if reasoning_decision.effective_reasoning_effort:
                log_extra_params["reasoning_effort"] = reasoning_decision.effective_reasoning_effort
        if tool_loop.full_reasoning:
            log_extra_params["reasoning_content"] = tool_loop.full_reasoning
        if outcome.usage_data:
            log_extra_params["usage"] = outcome.usage_data.model_dump()

        tool_loop.streaming_runtime.llm_logger.log_interaction(
            session_id=runtime.session_id,
            messages_sent=tool_loop.prompt_messages,
            response_received=response_msg,
            model=tool_loop.streaming_runtime.actual_model_id,
            extra_params=log_extra_params,
        )

    async def _persist_and_emit(
        self,
        *,
        runtime: SingleChatRuntime,
        outcome: SingleTurnOutcome,
    ) -> AsyncIterator[StreamEvent]:
        print("[Step 4] Saving complete AI response to file...")
        logger.info("[Step 4] Saving complete AI response")
        if outcome.tool_diagnostics:
            runtime.all_sources = merge_tool_diagnostics_into_sources(
                runtime.all_sources,
                outcome.tool_diagnostics,
            )
        assistant_message_id = await self.deps.post_turn_service.finalize_single_turn(
            session_id=runtime.session_id,
            assistant_message=outcome.full_response,
            usage_data=outcome.usage_data,
            cost_data=outcome.cost_data,
            sources=runtime.all_sources,
            raw_user_message=runtime.raw_user_message,
            assistant_id=runtime.assistant_id,
            assistant_memory_enabled=runtime.assistant_memory_enabled,
            user_message_id=runtime.user_message_id,
            context_type=runtime.context_type,
            project_id=runtime.project_id,
        )
        print(f"[OK] AI response saved with ID: {assistant_message_id}")

        if outcome.usage_data:
            usage_event = {
                "type": "usage",
                "usage": outcome.usage_data.model_dump(),
            }
            if outcome.cost_data:
                usage_event["cost"] = outcome.cost_data.model_dump()
            yield usage_event
        if runtime.all_sources:
            yield {
                "type": "sources",
                "sources": runtime.all_sources,
            }
        yield {
            "type": "assistant_message_id",
            "message_id": assistant_message_id,
        }
        followup_questions = await self.deps.post_turn_service.generate_followup_questions(
            session_id=runtime.session_id,
            context_type=runtime.context_type,
            project_id=runtime.project_id,
        )
        if followup_questions:
            yield {"type": "followup_questions", "questions": followup_questions}

    async def _maybe_auto_compress(
        self,
        *,
        session_id: str,
        model_id: str,
        messages: list[MessagePayload],
        context_type: str,
        project_id: str | None,
    ) -> tuple[list[MessagePayload], StreamEvent | None]:
        """Apply automatic compression when token estimate exceeds configured threshold."""
        try:
            compression_config_svc = self.deps.compression_config_service_factory()
            comp_config = compression_config_svc.config
            if not comp_config.auto_compress_enabled:
                return messages, None

            model_service = self.deps.model_service_factory()
            model_cfg, provider_cfg = model_service.get_model_and_provider_sync(model_id)
            context_length = (
                getattr(model_cfg.capabilities, "context_length", None)
                or getattr(provider_cfg.default_capabilities, "context_length", None)
                or 64000
            )
            threshold_tokens = int(context_length * comp_config.auto_compress_threshold)
            estimated_tokens = estimate_total_tokens(messages)
            if estimated_tokens <= threshold_tokens:
                return messages, None

            print(
                f"[AUTO-COMPRESS] Token estimate {estimated_tokens} > "
                f"threshold {threshold_tokens}, compressing..."
            )
            logger.info(
                "Auto-compression triggered: %s tokens > %s threshold",
                estimated_tokens,
                threshold_tokens,
            )
            compression_service = self.deps.compression_service_factory(self.deps.storage)
            result = await compression_service.compress_context(
                session_id=session_id,
                context_type=context_type,
                project_id=project_id,
            )
            if not result:
                print(
                    "[AUTO-COMPRESS] Compression returned no result, continuing without compression"
                )
                return messages, None

            compress_msg_id, compressed_count = result
            session = await self.deps.storage.get_session(
                session_id,
                context_type=context_type,
                project_id=project_id,
            )
            compressed_messages = session["state"]["messages"]
            print(f"[AUTO-COMPRESS] Done, compressed {compressed_count} messages")
            return compressed_messages, {
                "type": "auto_compressed",
                "compressed_count": compressed_count,
                "message_id": compress_msg_id,
            }
        except Exception as e:
            print(f"[AUTO-COMPRESS] Error (non-fatal): {str(e)}")
            logger.warning("Auto-compression failed (non-fatal): %s", str(e), exc_info=True)
            return messages, None

    async def _resolve_tools(
        self,
        *,
        request: ToolResolutionContext,
    ) -> tuple[list[Any] | None, Any | None]:
        """Resolve function-calling tools and optional assistant-scoped RAG tool executor."""
        resolved_tools = SingleChatResolvedTools()
        try:
            if not self._supports_function_calling(request.model_id):
                return None, None

            resolved_tools.llm_tools = list(self.deps.tool_registry_getter().get_all_tools())
            self._add_web_tools_if_needed(
                request=request,
                resolved_tools=resolved_tools,
            )
            await self._add_rag_tools_if_needed(
                request=request,
                resolved_tools=resolved_tools,
            )
            self._add_project_document_tools_if_needed(
                request=request,
                resolved_tools=resolved_tools,
            )
            resolved_tools.allowed_tool_names = await self._resolve_allowed_tool_names(
                request=request,
                candidate_tools=resolved_tools.llm_tools,
            )
            self._apply_project_tool_policy(
                request=request,
                resolved_tools=resolved_tools,
            )
            print(
                f"[TOOLS] Function calling enabled, {len(resolved_tools.llm_tools)} tools available"
            )
        except Exception as e:
            logger.warning(f"Failed to resolve tools: {e}")

        if not resolved_tools.tool_executors:
            return resolved_tools.llm_tools or None, None

        return (
            resolved_tools.llm_tools or None,
            self._build_combined_tool_executor(
                request=request,
                resolved_tools=resolved_tools,
            ),
        )

    def _supports_function_calling(self, model_id: str) -> bool:
        model_service = self.deps.model_service_factory()
        model_cfg, provider_cfg = model_service.get_model_and_provider_sync(model_id)
        merged_caps = model_service.get_merged_capabilities(model_cfg, provider_cfg)
        return bool(merged_caps.function_calling)

    def _add_web_tools_if_needed(
        self,
        *,
        request: ToolResolutionContext,
        resolved_tools: SingleChatResolvedTools,
    ) -> None:
        if not request.use_web_search:
            return

        web_tool_service = self.deps.web_tool_service_factory()
        web_tools = web_tool_service.get_tools()
        if not web_tools:
            return

        resolved_tools.llm_tools.extend(web_tools)
        resolved_tools.tool_executors.append(web_tool_service.execute_tool)
        print(f"[TOOLS] Added web tools: {len(web_tools)}")

    async def _add_rag_tools_if_needed(
        self,
        *,
        request: ToolResolutionContext,
        resolved_tools: SingleChatResolvedTools,
    ) -> None:
        kb_ids_for_tools = (
            await self.deps.project_knowledge_base_resolver_factory().resolve_effective_kb_ids(
                assistant_id=request.assistant_id,
                assistant_obj=request.assistant_obj,
                context_type=request.scope.context_type,
                project_id=request.scope.project_id,
            )
        )
        if not kb_ids_for_tools:
            return

        rag_tool_service = RagToolService(
            assistant_id=request.assistant_id
            or (
                f"project::{request.scope.project_id}"
                if request.scope.project_id
                else "project::default"
            ),
            allowed_kb_ids=kb_ids_for_tools,
            runtime_model_id=request.model_id,
        )
        rag_tools = rag_tool_service.get_tools()
        if not rag_tools:
            return

        resolved_tools.llm_tools.extend(rag_tools)
        resolved_tools.tool_executors.append(rag_tool_service.execute_tool)
        print(
            f"[TOOLS] Added RAG tools for assistant {request.assistant_id}: "
            f"{len(rag_tools)} tools, kb_count={len(kb_ids_for_tools)}"
        )

    def _add_project_document_tools_if_needed(
        self,
        *,
        request: ToolResolutionContext,
        resolved_tools: SingleChatResolvedTools,
    ) -> None:
        if request.scope.context_type != "project" or not request.scope.project_id:
            return

        doc_tool_service = self.deps.project_document_tool_service_factory(
            project_id=request.scope.project_id,
            session_id=request.scope.session_id,
            active_file_path=request.editor.active_file_path,
            active_file_hash=request.editor.active_file_hash,
        )
        doc_tools = doc_tool_service.get_tools()
        if not doc_tools:
            return

        resolved_tools.llm_tools.extend(doc_tools)
        resolved_tools.tool_executors.append(doc_tool_service.execute_tool)
        active_file_log = request.editor.active_file_path or "(none)"
        print(
            f"[TOOLS] Added project document tools: {len(doc_tools)} "
            f"(project={request.scope.project_id}, file={active_file_log})"
        )

    async def _resolve_allowed_tool_names(
        self,
        *,
        request: ToolResolutionContext,
        candidate_tools: list[Any],
    ) -> set[str]:
        return await self.deps.project_tool_policy_resolver_factory().get_allowed_tool_names(
            context_type=request.scope.context_type,
            project_id=request.scope.project_id,
            candidate_tool_names=[tool.name for tool in candidate_tools],
        )

    @staticmethod
    def _apply_project_tool_policy(
        *,
        request: ToolResolutionContext,
        resolved_tools: SingleChatResolvedTools,
    ) -> None:
        if request.scope.context_type != "project" or not request.scope.project_id:
            return

        resolved_tools.llm_tools = [
            tool
            for tool in resolved_tools.llm_tools
            if tool.name in resolved_tools.allowed_tool_names
        ]

    def _build_combined_tool_executor(
        self,
        *,
        request: ToolResolutionContext,
        resolved_tools: SingleChatResolvedTools,
    ) -> Callable[[str, dict[str, Any]], Awaitable[str | None]]:
        async def _combined_tool_executor(name: str, args: dict[str, Any]) -> str | None:
            if (
                request.scope.context_type == "project"
                and request.scope.project_id
                and name not in resolved_tools.allowed_tool_names
            ):
                logger.info(
                    "Blocked project tool by policy: %s (project=%s)",
                    name,
                    request.scope.project_id,
                )
                return f"Error: Tool '{name}' is disabled for this project"
            for executor in resolved_tools.tool_executors:
                try:
                    maybe_result = executor(name, args)
                    if asyncio.iscoroutine(maybe_result):
                        maybe_result = await maybe_result
                    if maybe_result is not None:
                        return str(maybe_result)
                except Exception as exec_error:
                    logger.warning("Tool executor failed for %s: %s", name, exec_error)
            return None

        return _combined_tool_executor
