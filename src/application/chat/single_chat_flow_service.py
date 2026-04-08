"""Single-chat streaming flow orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from src.application.chat.chat_runtime import (
    ChatOrchestrationRequest,
    SingleDirectOrchestrator,
    SingleDirectSettings,
)
from src.application.chat.client_tool_call_coordinator import (
    get_client_tool_call_coordinator,
)
from src.application.chat.rag_tool_service import RagToolService
from src.application.chat.request_contexts import (
    SingleChatRequestContext,
    ToolResolutionContext,
)
from src.application.chat.server_python_executor import execute_python_server_side_with_backend
from src.application.chat.service_contracts import (
    AssistantLike,
    ContextPayload,
    MessagePayload,
    SourcePayload,
    StreamEvent,
    StreamItem,
)
from src.application.chat.source_diagnostics import merge_tool_diagnostics_into_sources
from src.application.chat.tool_gate_service import ToolGateDecision, ToolGateService
from src.llm_runtime import estimate_total_tokens
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


def _default_assistant_tool_policy_resolver_factory() -> Any:
    from src.infrastructure.config.assistant_tool_policy_resolver import AssistantToolPolicyResolver

    return AssistantToolPolicyResolver()


def _default_code_execution_config_service_factory() -> Any:
    from src.infrastructure.config.code_execution_config_service import CodeExecutionConfigService

    return CodeExecutionConfigService()


def _default_tool_gate_config_service_factory() -> Any:
    from src.infrastructure.config.tool_gate_config_service import ToolGateConfigService

    return ToolGateConfigService()


def _default_tool_gate_service_factory() -> Any:
    return ToolGateService()


def _default_tool_description_config_service_factory() -> Any:
    from src.infrastructure.config.tool_description_config_service import (
        ToolDescriptionConfigService,
    )

    return ToolDescriptionConfigService()


def _default_tool_registry_getter() -> Any:
    from src.tools.registry import get_tool_registry

    return get_tool_registry()


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
    single_direct_orchestrator: SingleDirectOrchestrator | None = None
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
    assistant_tool_policy_resolver_factory: Callable[[], Any] = (
        _default_assistant_tool_policy_resolver_factory
    )
    code_execution_config_service_factory: Callable[[], Any] = (
        _default_code_execution_config_service_factory
    )
    tool_gate_config_service_factory: Callable[[], Any] = _default_tool_gate_config_service_factory
    tool_gate_service_factory: Callable[[], Any] = _default_tool_gate_service_factory
    tool_description_config_service_factory: Callable[[], Any] = (
        _default_tool_description_config_service_factory
    )
    tool_registry_getter: Callable[[], Any] = _default_tool_registry_getter


@dataclass
class SingleChatRuntime:
    """Single-turn runtime context resolved before stream starts."""

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
    """Collected outputs from one single-turn stream."""

    full_response: str = ""
    usage_data: TokenUsage | None = None
    cost_data: CostInfo | None = None
    tool_diagnostics: SourcePayload | None = None


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
    full_message_content: str
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

    _WEB_TOOL_NAMES = {"web_search", "read_webpage"}

    def __init__(self, deps: SingleChatFlowDeps):
        self.deps = deps
        self._single_direct_orchestrator = (
            deps.single_direct_orchestrator
            or SingleDirectOrchestrator(
                call_llm_stream=deps.call_llm_stream,
                file_service=deps.file_service,
            )
        )

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
        """Prepare context, run single-direct orchestration, and persist outputs."""
        is_temporary_turn = bool(request.stream.temporary_turn)
        runtime = await self._prepare_runtime(request=request)
        outcome = SingleTurnOutcome()

        if runtime.user_message_id:
            yield {
                "type": "user_message_id",
                "message_id": runtime.user_message_id,
            }
        else:
            if is_temporary_turn:
                print("[Step 1] Skipping user message save (temporary turn)")
                logger.info("[Step 1] Skipping user message save (temporary turn)")
            else:
                print("[Step 1] Skipping user message save (regeneration mode)")
                logger.info("[Step 1] Skipping user message save (regeneration mode)")

        if runtime.all_sources:
            yield {
                "type": "sources",
                "sources": runtime.all_sources,
            }
        if runtime.compression_event:
            yield runtime.compression_event
        llm_tools, tool_executor = await self._resolve_tools(
            request=ToolResolutionContext(
                scope=request.scope,
                editor=request.editor,
                assistant_id=runtime.assistant_id,
                assistant_obj=runtime.assistant_obj,
                model_id=runtime.model_id,
                use_web_search=request.search.use_web_search,
                user_message=runtime.raw_user_message,
            )
        )

        orchestration_request = ChatOrchestrationRequest(
            session_id=runtime.session_id,
            mode="single_direct",
            user_message=runtime.raw_user_message,
            participants=[runtime.assistant_id or "single_direct"],
            assistant_name_map={},
            assistant_config_map={},
            settings=SingleDirectSettings(
                messages=runtime.messages,
                model_id=runtime.model_id,
                system_prompt=runtime.system_prompt,
                max_rounds=runtime.max_rounds,
                context_segments=runtime.context_segments,
                assistant_params=runtime.assistant_params,
                reasoning_effort=request.stream.reasoning_effort,
                tools=llm_tools,
                tool_executor=tool_executor,
            ),
            reasoning_effort=request.stream.reasoning_effort,
            context_type=runtime.context_type,
            project_id=runtime.project_id,
        )

        try:
            async for event in self._single_direct_orchestrator.stream(orchestration_request):
                event_type = str(event.get("type") or "")
                if event_type == "assistant_chunk":
                    chunk = str(event.get("chunk") or "")
                    outcome.full_response += chunk
                    yield chunk
                    continue
                if event_type == "usage":
                    outcome.usage_data = self._normalize_usage(event.get("usage"))
                    continue
                if event_type == "tool_diagnostics":
                    outcome.tool_diagnostics = dict(event)
                    continue
                yield event
        except asyncio.CancelledError:
            print("[WARN] Stream generation cancelled, saving partial content...")
            logger.warning(
                "Single-direct stream cancelled, saving partial content (%s chars)",
                len(outcome.full_response),
            )
            if not is_temporary_turn:
                await self.deps.post_turn_service.save_partial_assistant_message(
                    session_id=runtime.session_id,
                    assistant_message=outcome.full_response,
                    context_type=runtime.context_type,
                    project_id=runtime.project_id,
                )
            raise

        self._apply_usage_to_outcome(
            runtime=runtime,
            outcome=outcome,
            usage_data=outcome.usage_data,
        )
        async for event in self._persist_and_emit(
            runtime=runtime,
            outcome=outcome,
            temporary_turn=is_temporary_turn,
        ):
            yield event

    @staticmethod
    def _normalize_usage(raw_usage: Any) -> TokenUsage | None:
        if isinstance(raw_usage, TokenUsage):
            return raw_usage
        if isinstance(raw_usage, dict):
            try:
                return TokenUsage(**raw_usage)
            except Exception:
                return None
        return None

    async def _prepare_runtime(
        self,
        *,
        request: SingleChatRequestContext,
    ) -> SingleChatRuntime:
        prepared_input = await self._prepare_single_chat_input(request=request)
        prepared_context = await self._prepare_single_chat_context(
            request=request,
            raw_user_message=prepared_input.raw_user_message,
            full_message_content=prepared_input.full_message_content,
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
            skip_user_append=request.stream.skip_user_append or request.stream.temporary_turn,
            context_type=request.scope.context_type,
            project_id=request.scope.project_id,
        )
        return SingleChatPreparedInput(
            raw_user_message=prepared_input.raw_user_message,
            full_message_content=prepared_input.full_message_content,
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
        full_message_content: str,
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

        messages = list(ctx.messages)
        if request.stream.temporary_turn:
            messages.append({"role": "user", "content": full_message_content})
        compression_event: StreamEvent | None = None
        if not request.stream.temporary_turn:
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
        if not self.deps.tool_registry_getter().is_plugin_loaded("web_tools"):
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

    async def _persist_and_emit(
        self,
        *,
        runtime: SingleChatRuntime,
        outcome: SingleTurnOutcome,
        temporary_turn: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        if outcome.tool_diagnostics:
            runtime.all_sources = merge_tool_diagnostics_into_sources(
                runtime.all_sources,
                outcome.tool_diagnostics,
            )

        if temporary_turn:
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
            return

        print("[Step 4] Saving complete AI response to file...")
        logger.info("[Step 4] Saving complete AI response")
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

            tool_registry = self.deps.tool_registry_getter()
            resolved_tools.llm_tools = list(tool_registry.get_all_tools())
            if not request.use_web_search:
                resolved_tools.llm_tools = [
                    tool
                    for tool in resolved_tools.llm_tools
                    if tool.name not in self._WEB_TOOL_NAMES
                ]
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
            self._apply_tool_policy(
                request=request,
                resolved_tools=resolved_tools,
            )
            self._apply_tool_description_overrides(resolved_tools=resolved_tools)
            gate_decision = self._apply_regex_tool_gate(
                request=request,
                resolved_tools=resolved_tools,
            )
            print(
                f"[TOOLS] Function calling enabled, {len(resolved_tools.llm_tools)} tools available"
            )
            if gate_decision.applied:
                print(
                    "[TOOLS] Gate matched rule "
                    f"{gate_decision.matched_rule_id} (priority={gate_decision.matched_rule_priority}), "
                    f"tools after gate: {len(resolved_tools.llm_tools)}"
                )
        except Exception as e:
            logger.warning(f"Failed to resolve tools: {e}")

        if not resolved_tools.llm_tools:
            return None, None
        return (
            resolved_tools.llm_tools or None,
            self._build_combined_tool_executor(
                request=request,
                resolved_tools=resolved_tools,
            ),
        )

    def _apply_tool_description_overrides(
        self,
        *,
        resolved_tools: SingleChatResolvedTools,
    ) -> None:
        if not resolved_tools.llm_tools:
            return
        config_service = self.deps.tool_description_config_service_factory()
        effective_map = (
            config_service.get_effective_description_map()
            if hasattr(config_service, "get_effective_description_map")
            else {}
        )
        if not effective_map:
            return
        overridden_tools: list[Any] = []
        for tool in resolved_tools.llm_tools:
            name = str(getattr(tool, "name", "") or "").strip()
            if not name or name not in effective_map:
                overridden_tools.append(tool)
                continue
            next_description = str(effective_map[name] or "").strip()
            if (
                not next_description
                or str(getattr(tool, "description", "") or "") == next_description
            ):
                overridden_tools.append(tool)
                continue
            if hasattr(tool, "model_copy"):
                overridden_tools.append(tool.model_copy(update={"description": next_description}))
            elif hasattr(tool, "copy"):
                overridden_tools.append(tool.copy(update={"description": next_description}))
            else:
                overridden_tools.append(tool)
        resolved_tools.llm_tools = overridden_tools

    def _apply_regex_tool_gate(
        self,
        *,
        request: ToolResolutionContext,
        resolved_tools: SingleChatResolvedTools,
    ) -> ToolGateDecision:
        candidate_names = {
            str(tool.name).strip()
            for tool in resolved_tools.llm_tools
            if str(getattr(tool, "name", "")).strip()
        }
        if not candidate_names:
            return ToolGateDecision(final_allowed_tool_names=set(), reason="no_candidate_tools")

        config_service = self.deps.tool_gate_config_service_factory()
        tool_gate_config = getattr(config_service, "config", None)
        if tool_gate_config is None:
            return ToolGateDecision(
                final_allowed_tool_names=set(candidate_names),
                reason="missing_tool_gate_config",
            )
        gate_service = self.deps.tool_gate_service_factory()
        decision = gate_service.apply(
            candidate_tool_names=set(candidate_names),
            user_message=request.user_message,
            config=tool_gate_config,
        )
        resolved_tools.allowed_tool_names = set(resolved_tools.allowed_tool_names).intersection(
            decision.final_allowed_tool_names
        )
        resolved_tools.llm_tools = [
            tool
            for tool in resolved_tools.llm_tools
            if tool.name in resolved_tools.allowed_tool_names
        ]
        return decision

    def _supports_function_calling(self, model_id: str) -> bool:
        model_service = self.deps.model_service_factory()
        model_cfg, provider_cfg = model_service.get_model_and_provider_sync(model_id)
        merged_caps = model_service.get_merged_capabilities(model_cfg, provider_cfg)
        return bool(merged_caps.function_calling)

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
        candidate_tool_names = [tool.name for tool in candidate_tools]
        assistant_allowed = (
            await self.deps.assistant_tool_policy_resolver_factory().get_allowed_tool_names(
                assistant_id=request.assistant_id,
                assistant_obj=request.assistant_obj,
                candidate_tool_names=candidate_tool_names,
            )
        )
        if request.scope.context_type != "project" or not request.scope.project_id:
            return {str(tool_name) for tool_name in assistant_allowed}

        project_allowed = (
            await self.deps.project_tool_policy_resolver_factory().get_allowed_tool_names(
                context_type=request.scope.context_type,
                project_id=request.scope.project_id,
                candidate_tool_names=candidate_tool_names,
            )
        )
        effective_allowed = set(assistant_allowed).intersection(project_allowed)
        return {str(tool_name) for tool_name in effective_allowed}

    @staticmethod
    def _apply_tool_policy(
        *,
        request: ToolResolutionContext,
        resolved_tools: SingleChatResolvedTools,
    ) -> None:
        _ = request
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
    ) -> Callable[..., Awaitable[str | None]]:
        async def _combined_tool_executor(
            name: str,
            args: dict[str, Any],
            tool_call_id: str = "",
        ) -> str | None:
            if name not in resolved_tools.allowed_tool_names:
                logger.info(
                    "Blocked tool by policy: %s (context=%s, project=%s, assistant=%s)",
                    name,
                    request.scope.context_type,
                    request.scope.project_id,
                    request.assistant_id,
                )
                if request.scope.context_type == "project" and request.scope.project_id:
                    return f"Error: Tool '{name}' is disabled for this project or assistant"
                return f"Error: Tool '{name}' is disabled for this assistant"
            if name == "execute_javascript":
                if not tool_call_id:
                    logger.warning(
                        "execute_javascript client method enabled but tool_call_id missing"
                    )
                    return "Error: execute_javascript requires client tool_call_id for browser execution"
                coordinator = get_client_tool_call_coordinator()
                try:
                    return await coordinator.await_result(
                        session_id=request.scope.session_id,
                        tool_call_id=tool_call_id,
                        timeout_s=max(
                            1.0,
                            min(
                                float(args.get("timeout_ms", 30000) or 30000) / 1000.0,
                                120.0,
                            ),
                        ),
                    )
                except asyncio.TimeoutError:
                    return json.dumps(
                        {
                            "ok": False,
                            "error": "JavaScript execution timed out waiting for browser runtime",
                        },
                        ensure_ascii=False,
                    )
                except Exception as client_error:
                    logger.warning("execute_javascript client method failed: %s", client_error)
                    return json.dumps(
                        {
                            "ok": False,
                            "error": f"JavaScript execution failed in browser runtime: {client_error}",
                        },
                        ensure_ascii=False,
                    )

            if name == "execute_python":
                code = str(args.get("code") or "")
                timeout_ms_raw = args.get("timeout_ms", 30000)
                try:
                    timeout_ms = int(timeout_ms_raw)
                except Exception:
                    timeout_ms = 30000
                timeout_ms = max(1000, min(timeout_ms, 120000))
                try:
                    code_execution_config = self.deps.code_execution_config_service_factory().config
                    enable_client_tool_execution = bool(
                        getattr(code_execution_config, "enable_client_tool_execution", True)
                    )
                    enable_server_jupyter_execution = bool(
                        getattr(code_execution_config, "enable_server_jupyter_execution", False)
                    )
                    enable_server_subprocess_execution = bool(
                        getattr(code_execution_config, "enable_server_subprocess_execution", False)
                    )
                    execution_priority = list(
                        getattr(
                            code_execution_config,
                            "execution_priority",
                            ["client", "server_jupyter", "server_subprocess"],
                        )
                    )
                    jupyter_kernel_name = str(
                        getattr(code_execution_config, "jupyter_kernel_name", "python3")
                    )
                except Exception as config_error:
                    logger.warning("Failed to load code execution config: %s", config_error)
                    enable_client_tool_execution = True
                    enable_server_jupyter_execution = False
                    enable_server_subprocess_execution = False
                    execution_priority = ["client", "server_jupyter", "server_subprocess"]
                    jupyter_kernel_name = "python3"

                allowed_methods = {
                    "client": enable_client_tool_execution,
                    "server_jupyter": enable_server_jupyter_execution,
                    "server_subprocess": enable_server_subprocess_execution,
                }
                normalized_priority: list[str] = []
                for method in execution_priority:
                    method_name = str(method or "").strip()
                    if (
                        method_name in {"client", "server_jupyter", "server_subprocess"}
                        and method_name not in normalized_priority
                    ):
                        normalized_priority.append(method_name)
                for method_name in ("client", "server_jupyter", "server_subprocess"):
                    if method_name not in normalized_priority:
                        normalized_priority.append(method_name)

                coordinator = get_client_tool_call_coordinator()

                for method_name in normalized_priority:
                    if not allowed_methods.get(method_name, False):
                        continue
                    if method_name == "client":
                        if not tool_call_id:
                            logger.warning(
                                "execute_python client method enabled but tool_call_id missing"
                            )
                            continue
                        try:
                            return await coordinator.await_result(
                                session_id=request.scope.session_id,
                                tool_call_id=tool_call_id,
                                timeout_s=timeout_ms / 1000.0,
                            )
                        except asyncio.TimeoutError:
                            logger.info(
                                "execute_python client method timed out after %sms, trying next method",
                                timeout_ms,
                            )
                            continue
                        except Exception as client_error:
                            logger.warning("execute_python client method failed: %s", client_error)
                            continue
                    if method_name == "server_jupyter":
                        return await execute_python_server_side_with_backend(
                            code=code,
                            timeout_ms=timeout_ms,
                            backend="jupyter",
                            jupyter_kernel_name=jupyter_kernel_name,
                        )
                    if method_name == "server_subprocess":
                        return await execute_python_server_side_with_backend(
                            code=code,
                            timeout_ms=timeout_ms,
                            backend="subprocess",
                            jupyter_kernel_name=jupyter_kernel_name,
                        )

                return (
                    "Error: execute_python failed because no enabled execution method succeeded "
                    "(check code execution settings)"
                )
            registry = self.deps.tool_registry_getter()
            registry_result = await registry.try_execute_tool_async(name, args)
            if registry_result is not None:
                return registry_result
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
