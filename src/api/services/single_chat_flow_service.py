"""Single-chat streaming flow orchestration extracted from AgentService."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Tuple

from src.agents.simple_llm import _estimate_total_tokens
from src.providers.types import CostInfo, TokenUsage

from .orchestration import OrchestrationRequest, SingleTurnOrchestrator, SingleTurnSettings
from .rag_tool_service import RagToolService
from .service_contracts import (
    AssistantLike,
    ContextPayload,
    MessagePayload,
    SourcePayload,
    StreamEvent,
    StreamItem,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SingleChatFlowDeps:
    """Dependencies required by SingleChatFlowService."""

    storage: Any
    chat_input_service: Any
    post_turn_service: Any
    single_turn_orchestrator: Any
    prepare_context: Callable[..., Awaitable[ContextPayload]]
    build_file_context_block: Callable[[Optional[List[Dict[str, str]]]], Awaitable[str]]
    merge_tool_diagnostics_into_sources: Callable[
        [List[SourcePayload], Optional[Dict[str, Any]]],
        List[SourcePayload],
    ]


@dataclass
class SingleChatRuntime:
    """Single-turn runtime context resolved before orchestration stream starts."""

    session_id: str
    context_type: str
    project_id: Optional[str]
    raw_user_message: str
    user_message_id: Optional[str]
    messages: List[MessagePayload]
    assistant_id: Optional[str]
    assistant_obj: Optional[AssistantLike]
    model_id: str
    system_prompt: Optional[str]
    context_segments: Dict[str, Optional[str]]
    assistant_params: Dict[str, Any]
    all_sources: List[SourcePayload]
    max_rounds: Optional[int]
    is_legacy_assistant: bool
    assistant_memory_enabled: bool
    active_file_path: Optional[str] = None
    active_file_hash: Optional[str] = None
    compression_event: Optional[StreamEvent] = None


@dataclass
class SingleTurnOutcome:
    """Collected outputs from one single-turn orchestration stream."""

    full_response: str = ""
    usage_data: Optional[TokenUsage] = None
    cost_data: Optional[CostInfo] = None
    tool_diagnostics: Optional[SourcePayload] = None


class SingleChatFlowService:
    """Runs single-chat stream flow and emits legacy-compatible events."""

    def __init__(self, deps: SingleChatFlowDeps):
        self.deps = deps

    async def process_message_stream(
        self,
        *,
        session_id: str,
        user_message: str,
        skip_user_append: bool = False,
        reasoning_effort: Optional[str] = None,
        attachments: Optional[List[SourcePayload]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
        active_file_path: Optional[str] = None,
        active_file_hash: Optional[str] = None,
    ) -> AsyncIterator[StreamItem]:
        """Prepare context, run single-turn orchestrator, and persist final outputs."""
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

        if runtime.user_message_id:
            yield {
                "type": "user_message_id",
                "message_id": runtime.user_message_id,
            }
        else:
            print(f"[Step 1] Skipping user message save (regeneration mode)")
            logger.info(f"[Step 1] Skipping user message save")

        if runtime.all_sources:
            yield {
                "type": "sources",
                "sources": runtime.all_sources,
            }
        if runtime.compression_event:
            yield runtime.compression_event

        llm_tools, rag_tool_executor = await self._resolve_tools(
            assistant_id=runtime.assistant_id,
            assistant_obj=runtime.assistant_obj,
            model_id=runtime.model_id,
            is_legacy_assistant=runtime.is_legacy_assistant,
            context_type=runtime.context_type,
            project_id=runtime.project_id,
            session_id=runtime.session_id,
            active_file_path=runtime.active_file_path,
            active_file_hash=runtime.active_file_hash,
            use_web_search=use_web_search,
        )
        outcome = SingleTurnOutcome()
        async for event in self._stream_single_turn(
            runtime=runtime,
            reasoning_effort=reasoning_effort,
            llm_tools=llm_tools,
            rag_tool_executor=rag_tool_executor,
            outcome=outcome,
        ):
            yield event
        async for event in self._persist_and_emit(runtime=runtime, outcome=outcome):
            yield event

    async def _prepare_runtime(
        self,
        *,
        session_id: str,
        user_message: str,
        skip_user_append: bool,
        attachments: Optional[List[SourcePayload]],
        context_type: str,
        project_id: Optional[str],
        use_web_search: bool,
        search_query: Optional[str],
        file_references: Optional[List[Dict[str, str]]],
        active_file_path: Optional[str],
        active_file_hash: Optional[str],
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

        print(f"[Step 2] Loading session state...")
        logger.info(f"[Step 2] Loading session state")
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
            is_legacy_assistant=ctx.is_legacy_assistant,
            assistant_memory_enabled=ctx.assistant_memory_enabled,
            active_file_path=(active_file_path or "").strip() or None,
            active_file_hash=(active_file_hash or "").strip() or None,
            compression_event=compression_event,
        )

    @staticmethod
    def _compose_system_prompt(*segments: Optional[str]) -> Optional[str]:
        parts = [str(segment).strip() for segment in segments if isinstance(segment, str) and segment.strip()]
        return "\n\n".join(parts) if parts else None

    def _strip_preloaded_web_context(
        self,
        *,
        context_segments: Dict[str, Optional[str]],
        all_sources: List[SourcePayload],
    ) -> Tuple[Optional[str], Dict[str, Optional[str]], List[SourcePayload]]:
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
            source for source in all_sources
            if source.get("type") not in {"search", "webpage"}
        ]
        return system_prompt, pruned_segments, filtered_sources

    async def _should_prefer_web_tools(
        self,
        *,
        session_id: str,
        context_type: str,
        project_id: Optional[str],
        use_web_search: bool,
    ) -> bool:
        if not use_web_search:
            return False

        try:
            from .model_config_service import ModelConfigService

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

            model_service = ModelConfigService()
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
        reasoning_effort: Optional[str],
        llm_tools: Optional[List[Any]],
        rag_tool_executor: Optional[Any],
        outcome: SingleTurnOutcome,
    ) -> AsyncIterator[StreamItem]:
        print(f"[Step 3] Streaming LLM call...")
        logger.info(f"[Step 3] Streaming LLM call")
        single_turn_request = OrchestrationRequest(
            session_id=runtime.session_id,
            mode="single_turn",
            user_message=runtime.raw_user_message,
            participants=[runtime.assistant_id] if runtime.assistant_id else [],
            assistant_name_map={},
            assistant_config_map={},
            settings=SingleTurnSettings(
                messages=runtime.messages,
                model_id=runtime.model_id,
                system_prompt=runtime.system_prompt,
                max_rounds=runtime.max_rounds,
                context_segments=runtime.context_segments,
                assistant_params=runtime.assistant_params,
                reasoning_effort=reasoning_effort,
                llm_tools=llm_tools,
                tool_executor=rag_tool_executor,
            ),
            reasoning_effort=reasoning_effort,
            context_type=runtime.context_type,
            project_id=runtime.project_id,
        )

        try:
            async for event in self.deps.single_turn_orchestrator.stream(single_turn_request):
                event_type = event.get("type")
                if event_type == "assistant_chunk":
                    chunk = str(event.get("chunk") or "")
                    outcome.full_response += chunk
                    yield chunk
                    continue
                if event_type in ("context_info", "thinking_duration", "tool_calls", "tool_results"):
                    yield event
                    continue
                if event_type == "usage":
                    usage_data = event.get("usage")
                    cost_data = event.get("cost")
                    if isinstance(usage_data, dict):
                        usage_data = TokenUsage(**usage_data)
                    if isinstance(cost_data, dict):
                        cost_data = CostInfo(**cost_data)
                    outcome.usage_data = usage_data
                    outcome.cost_data = cost_data
                    continue
                if event_type == "single_turn_complete":
                    (
                        outcome.full_response,
                        outcome.usage_data,
                        outcome.cost_data,
                        outcome.tool_diagnostics,
                    ) = SingleTurnOrchestrator.parse_completion_event(event)
                    continue
            print(f"[OK] LLM streaming complete")
            logger.info(f"[OK] LLM streaming complete")
            print(f"[MSG] AI response length: {len(outcome.full_response)} chars")
        except asyncio.CancelledError:
            print(f"[WARN] Stream generation cancelled, saving partial content...")
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
                print(f"[OK] Partial AI response saved")
            raise

    async def _persist_and_emit(
        self,
        *,
        runtime: SingleChatRuntime,
        outcome: SingleTurnOutcome,
    ) -> AsyncIterator[StreamEvent]:
        print(f"[Step 4] Saving complete AI response to file...")
        logger.info(f"[Step 4] Saving complete AI response")
        if outcome.tool_diagnostics:
            runtime.all_sources = self.deps.merge_tool_diagnostics_into_sources(
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
            is_legacy_assistant=runtime.is_legacy_assistant,
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
        messages: List[MessagePayload],
        context_type: str,
        project_id: Optional[str],
    ) -> Tuple[List[MessagePayload], Optional[StreamEvent]]:
        """Apply automatic compression when token estimate exceeds configured threshold."""
        try:
            from .compression_config_service import CompressionConfigService
            from .compression_service import CompressionService
            from .model_config_service import ModelConfigService

            compression_config_svc = CompressionConfigService()
            comp_config = compression_config_svc.config
            if not comp_config.auto_compress_enabled:
                return messages, None

            model_service = ModelConfigService()
            model_cfg, provider_cfg = model_service.get_model_and_provider_sync(model_id)
            context_length = (
                getattr(model_cfg.capabilities, "context_length", None)
                or getattr(provider_cfg.default_capabilities, "context_length", None)
                or 64000
            )
            threshold_tokens = int(context_length * comp_config.auto_compress_threshold)
            estimated_tokens = _estimate_total_tokens(messages)
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
            compression_service = CompressionService(self.deps.storage)
            result = await compression_service.compress_context(
                session_id=session_id,
                context_type=context_type,
                project_id=project_id,
            )
            if not result:
                print("[AUTO-COMPRESS] Compression returned no result, continuing without compression")
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
        assistant_id: Optional[str],
        assistant_obj: Optional[AssistantLike],
        model_id: str,
        is_legacy_assistant: bool,
        context_type: str,
        project_id: Optional[str],
        session_id: str,
        active_file_path: Optional[str],
        active_file_hash: Optional[str],
        use_web_search: bool,
    ) -> Tuple[Optional[List[Any]], Optional[Any]]:
        """Resolve function-calling tools and optional assistant-scoped RAG tool executor."""
        llm_tools: Optional[List[Any]] = None
        tool_executors: List[Any] = []
        allowed_tool_names: set[str] = set()
        try:
            from .model_config_service import ModelConfigService
            from .project_knowledge_base_resolver import ProjectKnowledgeBaseResolver
            from .project_document_tool_service import ProjectDocumentToolService
            from .project_tool_policy_resolver import ProjectToolPolicyResolver
            from .web_tool_service import WebToolService
            from src.tools.registry import get_tool_registry

            model_service = ModelConfigService()
            model_cfg, provider_cfg = model_service.get_model_and_provider_sync(model_id)
            merged_caps = model_service.get_merged_capabilities(model_cfg, provider_cfg)
            if not merged_caps.function_calling:
                return llm_tools, None

            llm_tools = list(get_tool_registry().get_all_tools())
            if use_web_search:
                web_tool_service = WebToolService()
                web_tools = web_tool_service.get_tools()
                if web_tools:
                    llm_tools.extend(web_tools)
                    tool_executors.append(web_tool_service.execute_tool)
                    print(f"[TOOLS] Added web tools: {len(web_tools)}")

            kb_ids_for_tools = await ProjectKnowledgeBaseResolver().resolve_effective_kb_ids(
                assistant_id=assistant_id,
                assistant_obj=assistant_obj,
                context_type=context_type,
                project_id=project_id,
            )
            if kb_ids_for_tools:
                rag_tool_service = RagToolService(
                    assistant_id=assistant_id or (f"project::{project_id}" if project_id else "project::default"),
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
                doc_tool_service = ProjectDocumentToolService(
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

            allowed_tool_names = await ProjectToolPolicyResolver().get_allowed_tool_names(
                context_type=context_type,
                project_id=project_id,
                candidate_tool_names=[tool.name for tool in llm_tools],
            )
            if context_type == "project" and project_id:
                llm_tools = [tool for tool in llm_tools if tool.name in allowed_tool_names]
            print(f"[TOOLS] Function calling enabled, {len(llm_tools)} tools available")
        except Exception as e:
            logger.warning(f"Failed to resolve tools: {e}")

        if not tool_executors:
            return llm_tools, None

        async def _combined_tool_executor(name: str, args: Dict[str, Any]) -> Optional[str]:
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
