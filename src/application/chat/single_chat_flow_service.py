"""Single-chat streaming flow orchestration."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.application.chat.rag_tool_service import RagToolService
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
from src.llm_runtime import (
    build_context_info_event,
    build_context_plan,
    context_segment_to_system_content,
    convert_to_langchain_messages,
    estimate_langchain_messages_tokens,
    estimate_total_tokens,
    filter_messages_by_context_boundary,
    get_context_limit,
    trim_to_context_limit,
)
from src.llm_runtime.stream_call_policy import build_stream_kwargs, select_stream_llm
from src.llm_runtime.streaming_client import _resolve_streaming_runtime
from src.llm_runtime.tool_loop_runner import ToolLoopRunner, ToolLoopState
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


class SingleChatFlowService:
    """Runs single-chat stream flow and emits chat stream events."""

    def __init__(self, deps: SingleChatFlowDeps):
        self.deps = deps
        self._orchestration_engine = OrchestrationEngine()

    async def process_message(
        self,
        *,
        session_id: str,
        user_message: str,
        context_type: str = "chat",
        project_id: str | None = None,
        use_web_search: bool = False,
        search_query: str | None = None,
        file_references: list[dict[str, str]] | None = None,
        active_file_path: str | None = None,
        active_file_hash: str | None = None,
    ) -> tuple[str, list[SourcePayload]]:
        """Collect the single-chat stream into one final response payload."""
        response_chunks: list[str] = []
        latest_sources: list[SourcePayload] = []

        async for event in self.process_message_stream(
            session_id=session_id,
            user_message=user_message,
            context_type=context_type,
            project_id=project_id,
            use_web_search=use_web_search,
            search_query=search_query,
            file_references=file_references,
            active_file_path=active_file_path,
            active_file_hash=active_file_hash,
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
        session_id: str,
        user_message: str,
        skip_user_append: bool = False,
        reasoning_effort: str | None = None,
        attachments: list[SourcePayload] | None = None,
        context_type: str = "chat",
        project_id: str | None = None,
        use_web_search: bool = False,
        search_query: str | None = None,
        file_references: list[dict[str, str]] | None = None,
        active_file_path: str | None = None,
        active_file_hash: str | None = None,
    ) -> AsyncIterator[StreamItem]:
        """Prepare context, run single-turn orchestration, and persist final outputs."""
        runtime_state: dict[str, Any] = {
            "runtime": None,
            "llm_tools": None,
            "rag_tool_executor": None,
            "tool_loop": None,
            "outcome": SingleTurnOutcome(),
        }
        run_id = f"single-chat-{session_id[:12]}-{uuid.uuid4().hex[:8]}"

        async def _prepare_runtime_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = await self._prepare_runtime(
                session_id=session_id,
                user_message=user_message,
                skip_user_append=skip_user_append,
                attachments=attachments,
                context_type=context_type,
                project_id=project_id,
                use_web_search=use_web_search,
                search_query=search_query,
                file_references=file_references,
                active_file_path=active_file_path,
                active_file_hash=active_file_hash,
            )
            runtime_state["runtime"] = runtime

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
            runtime = self._require_runtime_state(runtime_state)
            llm_tools, rag_tool_executor = await self._resolve_tools(
                assistant_id=runtime.assistant_id,
                assistant_obj=runtime.assistant_obj,
                model_id=runtime.model_id,
                context_type=runtime.context_type,
                project_id=runtime.project_id,
                session_id=runtime.session_id,
                active_file_path=runtime.active_file_path,
                active_file_hash=runtime.active_file_hash,
                use_web_search=use_web_search,
            )
            runtime_state["llm_tools"] = llm_tools
            runtime_state["rag_tool_executor"] = rag_tool_executor
            yield ActorResult()

        async def _choose_stream_path_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            has_tools = bool(runtime_state.get("llm_tools"))
            yield ActorResult(branch="tool_loop" if has_tools else "direct")

        async def _stream_direct_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = self._require_runtime_state(runtime_state)
            outcome = self._require_outcome_state(runtime_state)
            async for event in self._stream_single_turn(
                runtime=runtime,
                reasoning_effort=reasoning_effort,
                llm_tools=runtime_state["llm_tools"],
                rag_tool_executor=runtime_state["rag_tool_executor"],
                outcome=outcome,
            ):
                yield self._emit_single_chat_event(event)
            yield ActorResult()

        async def _prepare_tool_loop_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = self._require_runtime_state(runtime_state)
            tool_loop = await self._prepare_tool_loop_runtime(
                runtime=runtime,
                reasoning_effort=reasoning_effort,
                llm_tools=runtime_state["llm_tools"],
            )
            runtime_state["tool_loop"] = tool_loop
            yield self._emit_single_chat_event(tool_loop.context_info_event)
            yield ActorResult()

        async def _stream_tool_round_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = self._require_runtime_state(runtime_state)
            outcome = self._require_outcome_state(runtime_state)
            tool_loop = self._require_tool_loop_state(runtime_state)
            async for event in self._stream_tool_loop_round(
                runtime=runtime,
                tool_loop=tool_loop,
                outcome=outcome,
            ):
                yield self._emit_single_chat_event(event)
            yield ActorResult()

        async def _decide_tool_round_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            outcome = self._require_outcome_state(runtime_state)
            tool_loop = self._require_tool_loop_state(runtime_state)
            branch = self._decide_tool_loop_branch(
                tool_loop=tool_loop,
                outcome=outcome,
            )
            yield ActorResult(branch=branch)

        async def _execute_tools_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            tool_loop = self._require_tool_loop_state(runtime_state)
            async for event in self._execute_tool_loop_round(
                tool_loop=tool_loop,
                tool_executor=runtime_state["rag_tool_executor"],
            ):
                yield self._emit_single_chat_event(event)
            yield ActorResult()

        async def _finalize_tool_loop_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = self._require_runtime_state(runtime_state)
            outcome = self._require_outcome_state(runtime_state)
            tool_loop = self._require_tool_loop_state(runtime_state)
            async for event in self._finalize_tool_loop(
                runtime=runtime,
                outcome=outcome,
                tool_loop=tool_loop,
            ):
                yield self._emit_single_chat_event(event)
            yield ActorResult()

        async def _persist_result_actor(_: ActorExecutionContext) -> AsyncIterator[Any]:
            runtime = self._require_runtime_state(runtime_state)
            outcome = self._require_outcome_state(runtime_state)
            async for event in self._persist_and_emit(runtime=runtime, outcome=outcome):
                yield self._emit_single_chat_event(event)
            yield ActorResult(terminal_status="completed", terminal_reason="completed")

        spec = RunSpec(
            run_id=run_id,
            entry_node_id="prepare_runtime",
            nodes=(
                NodeSpec(
                    node_id="prepare_runtime",
                    actor=ActorRef(
                        actor_id="prepare_runtime",
                        kind="single_chat_prepare",
                        handler=_prepare_runtime_actor,
                    ),
                ),
                NodeSpec(
                    node_id="resolve_tools",
                    actor=ActorRef(
                        actor_id="resolve_tools",
                        kind="single_chat_tools",
                        handler=_resolve_tools_actor,
                    ),
                ),
                NodeSpec(
                    node_id="choose_stream_path",
                    actor=ActorRef(
                        actor_id="choose_stream_path",
                        kind="single_chat_branch",
                        handler=_choose_stream_path_actor,
                    ),
                ),
                NodeSpec(
                    node_id="stream_direct",
                    actor=ActorRef(
                        actor_id="stream_direct",
                        kind="single_chat_llm_direct",
                        handler=_stream_direct_actor,
                    ),
                ),
                NodeSpec(
                    node_id="prepare_tool_loop",
                    actor=ActorRef(
                        actor_id="prepare_tool_loop",
                        kind="single_chat_tool_loop_prepare",
                        handler=_prepare_tool_loop_actor,
                    ),
                ),
                NodeSpec(
                    node_id="stream_tool_round",
                    actor=ActorRef(
                        actor_id="stream_tool_round",
                        kind="single_chat_tool_loop_stream",
                        handler=_stream_tool_round_actor,
                    ),
                ),
                NodeSpec(
                    node_id="decide_tool_round",
                    actor=ActorRef(
                        actor_id="decide_tool_round",
                        kind="single_chat_tool_loop_branch",
                        handler=_decide_tool_round_actor,
                    ),
                ),
                NodeSpec(
                    node_id="execute_tools",
                    actor=ActorRef(
                        actor_id="execute_tools",
                        kind="single_chat_tool_loop_execute",
                        handler=_execute_tools_actor,
                    ),
                ),
                NodeSpec(
                    node_id="finalize_tool_loop",
                    actor=ActorRef(
                        actor_id="finalize_tool_loop",
                        kind="single_chat_tool_loop_finalize",
                        handler=_finalize_tool_loop_actor,
                    ),
                ),
                NodeSpec(
                    node_id="persist_result",
                    actor=ActorRef(
                        actor_id="persist_result",
                        kind="single_chat_persist",
                        handler=_persist_result_actor,
                    ),
                ),
            ),
            edges=(
                EdgeSpec(source_id="prepare_runtime", target_id="resolve_tools"),
                EdgeSpec(source_id="resolve_tools", target_id="choose_stream_path"),
                EdgeSpec(
                    source_id="choose_stream_path", target_id="stream_direct", branch="direct"
                ),
                EdgeSpec(
                    source_id="choose_stream_path",
                    target_id="prepare_tool_loop",
                    branch="tool_loop",
                ),
                EdgeSpec(source_id="stream_direct", target_id="persist_result"),
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
            ),
            metadata={"mode": "single_direct", "session_id": session_id},
        )
        context = RunContext(run_id=run_id, max_steps=24)

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
    def _require_runtime_state(runtime_state: dict[str, Any]) -> SingleChatRuntime:
        runtime = runtime_state.get("runtime")
        if not isinstance(runtime, SingleChatRuntime):
            raise RuntimeError("single chat runtime was not prepared before node execution")
        return runtime

    @staticmethod
    def _require_outcome_state(runtime_state: dict[str, Any]) -> SingleTurnOutcome:
        outcome = runtime_state.get("outcome")
        if not isinstance(outcome, SingleTurnOutcome):
            raise RuntimeError("single chat outcome state is unavailable")
        return outcome

    @staticmethod
    def _require_tool_loop_state(runtime_state: dict[str, Any]) -> SingleChatToolLoopRuntime:
        tool_loop = runtime_state.get("tool_loop")
        if not isinstance(tool_loop, SingleChatToolLoopRuntime):
            raise RuntimeError("single chat tool loop state is unavailable")
        return tool_loop

    async def _prepare_runtime(
        self,
        *,
        session_id: str,
        user_message: str,
        skip_user_append: bool,
        attachments: list[SourcePayload] | None,
        context_type: str,
        project_id: str | None,
        use_web_search: bool,
        search_query: str | None,
        file_references: list[dict[str, str]] | None,
        active_file_path: str | None,
        active_file_hash: str | None,
    ) -> SingleChatRuntime:
        original_user_message = user_message
        file_context_block = await self.deps.build_file_context_block(file_references)
        if file_context_block:
            user_message = f"{file_context_block}\n\n{user_message}"

        prepared_input = await self.deps.chat_input_service.prepare_user_input(
            session_id=session_id,
            raw_user_message=original_user_message,
            expanded_user_message=user_message,
            attachments=attachments,
            skip_user_append=skip_user_append,
            context_type=context_type,
            project_id=project_id,
        )

        print("[Step 2] Loading session state...")
        logger.info("[Step 2] Loading session state")
        prefer_web_tools = await self._should_prefer_web_tools(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
            use_web_search=use_web_search,
        )
        ctx = await self.deps.prepare_context(
            session_id=session_id,
            raw_user_message=prepared_input.raw_user_message,
            context_type=context_type,
            project_id=project_id,
            use_web_search=use_web_search and not prefer_web_tools,
            search_query=search_query,
        )
        print(f"[OK] Session loaded, {len(ctx.messages)} messages")
        print(f"   Assistant: {ctx.assistant_id}, Model: {ctx.model_id}")

        messages, compression_event = await self._maybe_auto_compress(
            session_id=session_id,
            model_id=ctx.model_id,
            messages=ctx.messages,
            context_type=context_type,
            project_id=project_id,
        )
        system_prompt = ctx.system_prompt
        context_segments = {
            "base_system_prompt": ctx.base_system_prompt,
            "memory_context": ctx.memory_context,
            "webpage_context": ctx.webpage_context,
            "search_context": ctx.search_context,
            "rag_context": ctx.rag_context,
            "structured_source_context": ctx.structured_source_context,
        }
        all_sources = list(ctx.all_sources)
        if prefer_web_tools:
            system_prompt, context_segments, all_sources = self._strip_preloaded_web_context(
                context_segments=context_segments,
                all_sources=all_sources,
            )

        return SingleChatRuntime(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
            raw_user_message=prepared_input.raw_user_message,
            user_message_id=prepared_input.user_message_id,
            messages=messages,
            assistant_id=ctx.assistant_id,
            assistant_obj=ctx.assistant_obj,
            model_id=ctx.model_id,
            system_prompt=system_prompt,
            context_segments=context_segments,
            assistant_params=ctx.assistant_params,
            all_sources=all_sources,
            max_rounds=ctx.max_rounds,
            assistant_memory_enabled=ctx.assistant_memory_enabled,
            active_file_path=(active_file_path or "").strip() or None,
            active_file_hash=(active_file_hash or "").strip() or None,
            compression_event=compression_event,
        )

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

        filtered_messages, summary_content = filter_messages_by_context_boundary(runtime.messages)
        max_input_tokens, context_window = get_context_limit(
            llm=streaming_runtime.llm,
            capabilities=streaming_runtime.capabilities,
        )
        context_plan = build_context_plan(
            messages=filtered_messages,
            system_prompt=runtime.system_prompt,
            context_segments=runtime.context_segments,
            summary_content=summary_content,
            max_rounds=runtime.max_rounds,
            context_budget_tokens=max_input_tokens,
        )

        langchain_messages: list[BaseMessage] = [
            SystemMessage(content=context_segment_to_system_content(segment.name, segment.content))
            for segment in context_plan.system_segments
        ]
        if self.deps.file_service:
            langchain_messages.extend(
                await convert_to_langchain_messages(
                    context_plan.chat_messages,
                    runtime.session_id,
                    self.deps.file_service,
                )
            )
        else:
            for message in context_plan.chat_messages:
                role = str(message.get("role") or "").strip().lower()
                if role == "user":
                    langchain_messages.append(
                        HumanMessage(content=str(message.get("content") or ""))
                    )
                elif role == "assistant":
                    langchain_messages.append(AIMessage(content=str(message.get("content") or "")))

        prompt_messages = trim_to_context_limit(langchain_messages, max_input_tokens)
        estimated_prompt_tokens = estimate_langchain_messages_tokens(prompt_messages)
        context_info_event = build_context_info_event(
            context_plan=context_plan,
            context_budget=max_input_tokens,
            context_window=context_window,
            estimated_prompt_tokens=estimated_prompt_tokens,
        )

        llm_for_tools = streaming_runtime.llm
        tools_enabled = False
        if llm_tools:
            try:
                llm_for_tools = streaming_runtime.llm.bind_tools(llm_tools)
                tools_enabled = True
            except Exception as exc:
                logger.warning("Failed to bind tools for single-chat tool loop: %s", exc)

        latest_user_text = ""
        for raw_message in reversed(runtime.messages):
            if str(raw_message.get("role", "")).strip().lower() == "user":
                latest_user_text = str(raw_message.get("content") or "")
                break

        tool_names = (
            {
                str(getattr(tool, "name", "") or "").strip()
                for tool in (llm_tools or [])
                if str(getattr(tool, "name", "") or "").strip()
            }
            if tools_enabled
            else set()
        )
        max_tool_rounds = ToolLoopRunner.resolve_max_tool_rounds(
            tool_names=tool_names,
            latest_user_text=latest_user_text,
            default_max_tool_rounds=3,
        )
        tool_loop_runner = ToolLoopRunner(max_tool_rounds=max_tool_rounds)
        tool_loop_state = ToolLoopState(
            current_messages=list(prompt_messages),
            web_research_enabled=bool(tool_names.intersection({"web_search", "read_webpage"})),
            max_tool_rounds=max_tool_rounds,
        )
        tool_loop_state.evidence_intent = tool_loop_runner.detect_evidence_intent(latest_user_text)

        return SingleChatToolLoopRuntime(
            streaming_runtime=streaming_runtime,
            llm_for_tools=llm_for_tools,
            tool_loop_runner=tool_loop_runner,
            tool_loop_state=tool_loop_state,
            prompt_messages=list(prompt_messages),
            context_info_event=context_info_event,
            tools_enabled=tools_enabled,
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
            active_llm = select_stream_llm(
                llm=tool_loop.streaming_runtime.llm,
                llm_for_tools=tool_loop.llm_for_tools,
                tools_enabled=tool_loop.tools_enabled,
                force_finalize_without_tools=tool_loop.tool_loop_state.force_finalize_without_tools,
            )
            stream_kwargs = build_stream_kwargs(
                allow_responses_fallback=tool_loop.streaming_runtime.allow_responses_fallback,
            )

            in_thinking_phase = False
            thinking_ended = False
            thinking_start_time: float | None = None
            tool_loop.round_content = ""
            tool_loop.round_reasoning = ""
            tool_loop.round_reasoning_details = None
            tool_loop.merged_chunk = None
            tool_loop.pending_tool_calls = []

            async for chunk in tool_loop.streaming_runtime.adapter.stream(
                active_llm,
                tool_loop.tool_loop_state.current_messages,
                **stream_kwargs,
            ):
                chunk_usage = getattr(chunk, "usage", None)
                if isinstance(chunk_usage, dict):
                    chunk_usage = TokenUsage(**chunk_usage)
                if chunk_usage is not None:
                    tool_loop.final_usage = chunk_usage

                if (
                    chunk.thinking
                    and not tool_loop.streaming_runtime.reasoning_decision.disable_thinking
                ):
                    tool_loop.full_reasoning += chunk.thinking
                    tool_loop.round_reasoning += chunk.thinking
                    if not in_thinking_phase:
                        in_thinking_phase = True
                        thinking_start_time = time.time()
                        yield "<think>"
                    yield chunk.thinking

                if chunk.content:
                    if in_thinking_phase and not thinking_ended:
                        thinking_ended = True
                        duration_ms = (
                            int((time.time() - thinking_start_time) * 1000)
                            if thinking_start_time is not None
                            else 0
                        )
                        yield "</think>"
                        yield {"type": "thinking_duration", "duration_ms": duration_ms}
                    tool_loop.round_content += chunk.content
                    yield chunk.content

                if chunk.raw is not None:
                    try:
                        tool_loop.merged_chunk = (
                            chunk.raw
                            if tool_loop.merged_chunk is None
                            else tool_loop.merged_chunk + chunk.raw
                        )
                    except Exception:
                        pass

            if tool_loop.merged_chunk is not None:
                extracted_usage = TokenUsage.extract_from_chunk(tool_loop.merged_chunk)
                if extracted_usage and tool_loop.final_usage is None:
                    tool_loop.final_usage = extracted_usage
                if (
                    not tool_loop.streaming_runtime.reasoning_decision.disable_thinking
                    and not tool_loop.round_reasoning
                ):
                    merged_kwargs = getattr(tool_loop.merged_chunk, "additional_kwargs", None) or {}
                    if isinstance(merged_kwargs, dict):
                        merged_reasoning = merged_kwargs.get("reasoning_content")
                        if isinstance(merged_reasoning, str) and merged_reasoning:
                            tool_loop.round_reasoning = merged_reasoning
                            tool_loop.full_reasoning += merged_reasoning
                merged_kwargs = getattr(tool_loop.merged_chunk, "additional_kwargs", None) or {}
                if isinstance(merged_kwargs, dict):
                    tool_loop.round_reasoning_details = merged_kwargs.get("reasoning_details")

            tool_loop.pending_tool_calls = tool_loop.tool_loop_runner.extract_tool_calls(
                tool_loop.merged_chunk,
                tools_enabled=tool_loop.tools_enabled,
                force_finalize_without_tools=tool_loop.tool_loop_state.force_finalize_without_tools,
            )

            if in_thinking_phase and not thinking_ended:
                duration_ms = (
                    int((time.time() - thinking_start_time) * 1000)
                    if thinking_start_time is not None
                    else 0
                )
                yield "</think>"
                yield {"type": "thinking_duration", "duration_ms": duration_ms}

            outcome.full_response += tool_loop.round_content
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
        round_tool_calls = tool_loop.pending_tool_calls
        if tool_loop.tool_loop_runner.should_request_read_compensation(
            tool_loop.tool_loop_state,
            round_tool_calls=round_tool_calls,
        ):
            if tool_loop.round_content and outcome.full_response.endswith(tool_loop.round_content):
                outcome.full_response = outcome.full_response[: -len(tool_loop.round_content)]
            logger.info("Injecting read_knowledge compensation prompt for evidence-focused request")
            tool_loop.tool_loop_runner.apply_read_compensation_prompt(tool_loop.tool_loop_state)
            return "continue"

        if tool_loop.tool_loop_runner.should_request_web_read_compensation(
            tool_loop.tool_loop_state,
            round_tool_calls=round_tool_calls,
        ):
            if tool_loop.round_content and outcome.full_response.endswith(tool_loop.round_content):
                outcome.full_response = outcome.full_response[: -len(tool_loop.round_content)]
            logger.info("Injecting read_webpage compensation prompt for web research request")
            tool_loop.tool_loop_runner.apply_web_read_compensation_prompt(tool_loop.tool_loop_state)
            return "continue"

        if tool_loop.tool_loop_runner.should_finish_round(
            tool_loop.tool_loop_state,
            round_tool_calls=round_tool_calls,
            tools_enabled=tool_loop.tools_enabled,
        ):
            return "finalize"

        if tool_loop.tool_loop_runner.advance_round_or_force_finalize(
            tool_loop.tool_loop_state,
            round_content=tool_loop.round_content,
            round_reasoning=tool_loop.round_reasoning,
            round_reasoning_details=tool_loop.round_reasoning_details,
        ):
            logger.info("Single-chat tool loop entered force-finalize mode")
            return "continue"

        return "execute_tools"

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

        tool_results = await tool_loop.tool_loop_runner.execute_tool_calls(
            round_tool_calls,
            tool_executor=tool_executor,
        )
        tool_loop.tool_loop_runner.record_round_activity(
            tool_loop.tool_loop_state,
            round_tool_calls=round_tool_calls,
            tool_results=tool_results,
        )
        yield tool_loop.tool_loop_runner.build_tool_results_event(tool_results)
        tool_loop.tool_loop_runner.append_round_with_tool_results(
            tool_loop.tool_loop_state,
            round_content=tool_loop.round_content,
            round_tool_calls=round_tool_calls,
            tool_results=tool_results,
            round_reasoning=tool_loop.round_reasoning,
            round_reasoning_details=tool_loop.round_reasoning_details,
        )
        tool_loop.pending_tool_calls = []

    async def _finalize_tool_loop(
        self,
        *,
        runtime: SingleChatRuntime,
        outcome: SingleTurnOutcome,
        tool_loop: SingleChatToolLoopRuntime,
    ) -> AsyncIterator[StreamItem]:
        if tool_loop.tool_loop_runner.should_inject_fallback_answer(
            tool_loop.tool_loop_state,
            outcome.full_response,
        ):
            injected = tool_loop.tool_loop_runner.build_fallback_answer(tool_loop.tool_loop_state)
            if outcome.full_response.strip():
                injected = f"\n\n{injected}"
            outcome.full_response += injected
            tool_loop.tool_loop_state.tool_finalize_reason = "fallback_empty_answer"
            yield injected

        outcome.tool_diagnostics = tool_loop.tool_loop_runner.build_tool_diagnostics_event(
            tool_loop.tool_loop_state
        )
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
        assistant_id: str | None,
        assistant_obj: AssistantLike | None,
        model_id: str,
        context_type: str,
        project_id: str | None,
        session_id: str,
        active_file_path: str | None,
        active_file_hash: str | None,
        use_web_search: bool,
    ) -> tuple[list[Any] | None, Any | None]:
        """Resolve function-calling tools and optional assistant-scoped RAG tool executor."""
        llm_tools: list[Any] | None = None
        tool_executors: list[Any] = []
        allowed_tool_names: set[str] = set()
        try:
            model_service = self.deps.model_service_factory()
            model_cfg, provider_cfg = model_service.get_model_and_provider_sync(model_id)
            merged_caps = model_service.get_merged_capabilities(model_cfg, provider_cfg)
            if not merged_caps.function_calling:
                return llm_tools, None

            llm_tools = list(self.deps.tool_registry_getter().get_all_tools())
            if use_web_search:
                web_tool_service = self.deps.web_tool_service_factory()
                web_tools = web_tool_service.get_tools()
                if web_tools:
                    llm_tools.extend(web_tools)
                    tool_executors.append(web_tool_service.execute_tool)
                    print(f"[TOOLS] Added web tools: {len(web_tools)}")

            kb_ids_for_tools = (
                await self.deps.project_knowledge_base_resolver_factory().resolve_effective_kb_ids(
                    assistant_id=assistant_id,
                    assistant_obj=assistant_obj,
                    context_type=context_type,
                    project_id=project_id,
                )
            )
            if kb_ids_for_tools:
                rag_tool_service = RagToolService(
                    assistant_id=assistant_id
                    or (f"project::{project_id}" if project_id else "project::default"),
                    allowed_kb_ids=kb_ids_for_tools,
                    runtime_model_id=model_id,
                )
                rag_tools = rag_tool_service.get_tools()
                if rag_tools:
                    llm_tools.extend(rag_tools)
                    tool_executors.append(rag_tool_service.execute_tool)
                    print(
                        f"[TOOLS] Added RAG tools for assistant {assistant_id}: "
                        f"{len(rag_tools)} tools, kb_count={len(kb_ids_for_tools)}"
                    )

            if context_type == "project" and project_id:
                doc_tool_service = self.deps.project_document_tool_service_factory(
                    project_id=project_id,
                    session_id=session_id,
                    active_file_path=active_file_path,
                    active_file_hash=active_file_hash,
                )
                doc_tools = doc_tool_service.get_tools()
                if doc_tools:
                    llm_tools.extend(doc_tools)
                    tool_executors.append(doc_tool_service.execute_tool)
                    active_file_log = active_file_path or "(none)"
                    print(
                        f"[TOOLS] Added project document tools: {len(doc_tools)} "
                        f"(project={project_id}, file={active_file_log})"
                    )

            allowed_tool_names = (
                await self.deps.project_tool_policy_resolver_factory().get_allowed_tool_names(
                    context_type=context_type,
                    project_id=project_id,
                    candidate_tool_names=[tool.name for tool in llm_tools],
                )
            )
            if context_type == "project" and project_id:
                llm_tools = [tool for tool in llm_tools if tool.name in allowed_tool_names]
            print(f"[TOOLS] Function calling enabled, {len(llm_tools)} tools available")
        except Exception as e:
            logger.warning(f"Failed to resolve tools: {e}")

        if not tool_executors:
            return llm_tools, None

        async def _combined_tool_executor(name: str, args: dict[str, Any]) -> str | None:
            if context_type == "project" and project_id and name not in allowed_tool_names:
                logger.info("Blocked project tool by policy: %s (project=%s)", name, project_id)
                return f"Error: Tool '{name}' is disabled for this project"
            for executor in tool_executors:
                try:
                    maybe_result = executor(name, args)
                    if asyncio.iscoroutine(maybe_result):
                        maybe_result = await maybe_result
                    if maybe_result is not None:
                        return str(maybe_result)
                except Exception as exec_error:
                    logger.warning("Tool executor failed for %s: %s", name, exec_error)
            return None

        return llm_tools, _combined_tool_executor
