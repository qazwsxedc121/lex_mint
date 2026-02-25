"""Agent service for processing chat messages - Simplified version (without LangGraph)"""

from dataclasses import dataclass
from typing import Dict, AsyncIterator, Optional, Any, List, Tuple, cast
import logging
import uuid
import re
import os
import json
from types import SimpleNamespace

from src.agents.simple_llm import call_llm, call_llm_stream
from .agent_service_bootstrap import bootstrap_agent_service
from .chat_input_service import ChatInputService
from .compare_flow_service import CompareFlowDeps, CompareFlowService
from .context_assembly_service import ContextAssemblyService
from .conversation_storage import ConversationStorage
from .file_reference_config_service import FileReferenceConfig
from .group_participants import parse_group_participant
from .group_chat_service import GroupChatDeps, GroupChatService
from .group_orchestration import (
    CompareModelsOrchestrator,
    CommitteeOrchestrator,
    CommitteePolicy,
    GroupSettingsResolver,
    RoundRobinOrchestrator,
    SingleTurnOrchestrator,
    CommitteeRuntimeState,
    CommitteeTurnExecutor,
)
from .post_turn_service import PostTurnService
from .service_contracts import AssistantLike, ContextPayload
from .single_chat_flow_service import SingleChatFlowDeps, SingleChatFlowService
from .group_orchestration.log_utils import build_messages_preview_for_log, truncate_log_text

logger = logging.getLogger(__name__)


@dataclass
class _RuntimeAssistant:
    id: str
    name: str
    model_id: str
    icon: str
    description: str
    system_prompt: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    top_p: Optional[float]
    top_k: Optional[int]
    frequency_penalty: Optional[float]
    presence_penalty: Optional[float]
    max_rounds: Optional[int]
    memory_enabled: bool
    knowledge_base_ids: Optional[List[str]]
    enabled: bool


class AgentService:
    """Service layer for agent interactions with conversation storage.

    Coordinates the flow:
    1. Append user message to storage
    2. Load current conversation state
    3. Call LLM to generate response (direct call, without LangGraph)
    4. Append assistant response to storage
    5. Return response to caller
    """

    def __init__(self, storage: ConversationStorage):
        """Initialize agent service.

        Args:
            storage: ConversationStorage instance for persistence
        """
        bootstrap_agent_service(self, storage)
        logger.info("AgentService initialized (simplified version)")

    _FILE_CONTEXT_CHUNK_SIZE = 2500
    _FILE_CONTEXT_MAX_CHUNKS = 6
    _FILE_CONTEXT_PREVIEW_CHARS = 600
    _FILE_CONTEXT_PREVIEW_LINES = 40
    _FILE_CONTEXT_TOTAL_BUDGET_CHARS = 18000
    _GROUP_TRACE_PREVIEW_CHARS = 1600

    # Runtime-initialized service dependencies (set by bootstrap).
    storage: ConversationStorage
    pricing_service: Any
    file_service: Any
    search_service: Any
    webpage_service: Any
    memory_service: Any
    file_reference_config_service: Any
    rag_config_service: Any
    source_context_service: Any
    comparison_storage: Any
    _committee_policy: CommitteePolicy

    @staticmethod
    def _truncate_log_text(text: Optional[str], max_chars: int = 1600) -> str:
        """Trim text for debug logs while preserving head and tail context."""
        return truncate_log_text(text, max_chars)

    @staticmethod
    def _build_messages_preview_for_log(
        messages: List[Dict[str, Any]],
        *,
        max_messages: int = 10,
        max_chars: int = 220,
    ) -> List[Dict[str, Any]]:
        """Build a compact recent message view for group context debugging."""
        return build_messages_preview_for_log(
            messages,
            max_messages=max_messages,
            max_chars=max_chars,
        )

    @staticmethod
    def _is_group_trace_enabled() -> bool:
        """Enable verbose group trace logging via env variable."""
        value = os.getenv("LEX_MINT_GROUP_TRACE", "").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def _log_group_trace(self, trace_id: str, stage: str, payload: Dict[str, Any]) -> None:
        """Emit structured group-trace logs when tracing is enabled."""
        if not self._is_group_trace_enabled():
            return
        try:
            serialized = json.dumps(payload, ensure_ascii=True, default=str)
        except Exception:
            serialized = str(payload)
        logger.info("[GroupTrace][%s][%s] %s", trace_id, stage, serialized)

    def _create_committee_turn_executor(self) -> CommitteeTurnExecutor:
        """Build turn executor with service dependencies and prompt/context callbacks."""
        return CommitteeTurnExecutor(
            storage=self.storage,
            pricing_service=self.pricing_service,
            memory_service=self.memory_service,
            file_service=self.file_service,
            assistant_params_from_config=self._assistant_params_from_config,
            build_group_history_hint=self._build_group_history_hint,
            build_group_identity_prompt=self._build_group_identity_prompt,
            build_group_instruction_prompt=self._build_group_instruction_prompt,
            build_rag_context_and_sources=self._build_rag_context_and_sources,
            truncate_log_text=self._truncate_log_text,
            build_messages_preview_for_log=self._build_messages_preview_for_log,
            log_group_trace=self._log_group_trace,
            group_trace_preview_chars=self._GROUP_TRACE_PREVIEW_CHARS,
        )

    def _get_committee_turn_executor(self) -> CommitteeTurnExecutor:
        """Lazily initialize turn executor for tests that construct AgentService via __new__."""
        executor = getattr(self, "_committee_turn_executor", None)
        if executor is None:
            executor = self._create_committee_turn_executor()
            self._committee_turn_executor = executor
        return executor

    def _create_committee_orchestrator(self) -> CommitteeOrchestrator:
        """Build committee orchestrator from current service callbacks."""
        return CommitteeOrchestrator(
            llm_call=call_llm,
            assistant_params_from_config=self._assistant_params_from_config,
            stream_group_assistant_turn=self._stream_group_assistant_turn,
            get_message_content_by_id=self._get_message_content_by_id,
            build_structured_turn_summary=self._build_structured_turn_summary,
            build_committee_turn_packet=self._build_committee_turn_packet,
            detect_group_role_drift=self._detect_group_role_drift,
            build_role_retry_instruction=self._build_role_retry_instruction,
            truncate_log_text=self._truncate_log_text,
            log_group_trace=self._log_group_trace,
            group_trace_preview_chars=self._GROUP_TRACE_PREVIEW_CHARS,
        )

    def _create_round_robin_orchestrator(self) -> RoundRobinOrchestrator:
        """Build round-robin orchestrator from current service callbacks."""
        return RoundRobinOrchestrator(
            stream_group_assistant_turn=self._stream_group_assistant_turn,
        )

    def _create_single_turn_orchestrator(self) -> SingleTurnOrchestrator:
        """Build single-turn orchestrator for standard chat streaming."""
        return SingleTurnOrchestrator(
            call_llm_stream=call_llm_stream,
            pricing_service=self.pricing_service,
            file_service=self.file_service,
        )

    def _create_compare_models_orchestrator(self) -> CompareModelsOrchestrator:
        """Build compare-models orchestrator for multi-model streaming."""
        return CompareModelsOrchestrator(
            call_llm_stream=call_llm_stream,
            pricing_service=self.pricing_service,
            file_service=self.file_service,
            resolve_model_name=self._resolve_compare_model_name,
        )

    def _get_single_turn_orchestrator(self) -> SingleTurnOrchestrator:
        """Lazily initialize single-turn orchestrator for tests using __new__."""
        orchestrator = getattr(self, "_single_turn_orchestrator", None)
        if orchestrator is None:
            orchestrator = self._create_single_turn_orchestrator()
            self._single_turn_orchestrator = orchestrator
        return orchestrator

    def _get_compare_models_orchestrator(self) -> CompareModelsOrchestrator:
        """Lazily initialize compare-models orchestrator for tests using __new__."""
        orchestrator = getattr(self, "_compare_models_orchestrator", None)
        if orchestrator is None:
            orchestrator = self._create_compare_models_orchestrator()
            self._compare_models_orchestrator = orchestrator
        return orchestrator

    def _create_group_chat_service(self) -> GroupChatService:
        """Build group chat service facade for group-mode runtime flow."""
        chat_input_service = getattr(self, "chat_input_service", None)
        if chat_input_service is None and hasattr(self, "storage") and hasattr(self, "file_service"):
            chat_input_service = self._get_chat_input_service()

        post_turn_service = getattr(self, "post_turn_service", None)
        if post_turn_service is None and hasattr(self, "storage") and hasattr(self, "memory_service"):
            post_turn_service = self._get_post_turn_service()

        if chat_input_service is None:
            async def _missing_prepare_user_input(**_kwargs):
                raise RuntimeError("chat_input_service is not initialized")

            chat_input_service = SimpleNamespace(prepare_user_input=_missing_prepare_user_input)

        if post_turn_service is None:
            async def _noop_schedule_title_generation(**_kwargs):
                return None

            post_turn_service = SimpleNamespace(schedule_title_generation=_noop_schedule_title_generation)

        search_service = getattr(self, "search_service", None)
        if search_service is None:
            async def _empty_search(_query):
                return []

            search_service = SimpleNamespace(
                search=_empty_search,
                build_search_context=lambda _query, _sources: None,
            )

        return GroupChatService(
            GroupChatDeps(
                chat_input_service=cast(ChatInputService, chat_input_service),
                post_turn_service=cast(PostTurnService, post_turn_service),
                search_service=cast(Any, search_service),
                build_file_context_block=self._build_file_context_block,
                build_group_runtime_assistant=self._build_group_runtime_assistant,
                resolve_group_settings=self._resolve_group_settings,
                create_committee_orchestrator=self._create_committee_orchestrator,
                create_round_robin_orchestrator=self._create_round_robin_orchestrator,
                is_group_trace_enabled=self._is_group_trace_enabled,
                log_group_trace=self._log_group_trace,
                truncate_log_text=self._truncate_log_text,
                group_trace_preview_chars=self._GROUP_TRACE_PREVIEW_CHARS,
            )
        )

    def _get_group_chat_service(self) -> GroupChatService:
        """Lazily initialize group chat service for tests using __new__."""
        service = getattr(self, "_group_chat_service", None)
        if service is None:
            service = self._create_group_chat_service()
            self._group_chat_service = service
        return service

    def _create_single_chat_flow_service(self) -> SingleChatFlowService:
        """Build single-chat flow service facade for standard chat stream."""
        return SingleChatFlowService(
            SingleChatFlowDeps(
                storage=self.storage,
                chat_input_service=self._get_chat_input_service(),
                post_turn_service=self._get_post_turn_service(),
                single_turn_orchestrator=self._get_single_turn_orchestrator(),
                prepare_context=self._prepare_context,
                build_file_context_block=self._build_file_context_block,
                merge_tool_diagnostics_into_sources=self._merge_tool_diagnostics_into_sources,
            )
        )

    def _get_single_chat_flow_service(self) -> SingleChatFlowService:
        """Lazily initialize single-chat flow service for tests using __new__."""
        service = getattr(self, "_single_chat_flow_service", None)
        if service is None:
            service = self._create_single_chat_flow_service()
            self._single_chat_flow_service = service
        return service

    def _create_compare_flow_service(self) -> CompareFlowService:
        """Build compare flow service facade for compare-model stream."""
        return CompareFlowService(
            CompareFlowDeps(
                storage=self.storage,
                comparison_storage=self.comparison_storage,
                chat_input_service=self._get_chat_input_service(),
                compare_models_orchestrator=self._get_compare_models_orchestrator(),
                prepare_context=self._prepare_context,
                build_file_context_block=self._build_file_context_block,
            )
        )

    def _get_compare_flow_service(self) -> CompareFlowService:
        """Lazily initialize compare flow service for tests using __new__."""
        service = getattr(self, "_compare_flow_service", None)
        if service is None:
            service = self._create_compare_flow_service()
            self._compare_flow_service = service
        return service

    def _create_chat_input_service(self) -> ChatInputService:
        """Build shared chat-input service for attachments and user append."""
        return ChatInputService(self.storage, self.file_service)

    def _get_chat_input_service(self) -> ChatInputService:
        """Lazily initialize chat-input service for tests using __new__."""
        service = getattr(self, "chat_input_service", None)
        if service is None:
            service = self._create_chat_input_service()
            self.chat_input_service = service
        return service

    def _create_post_turn_service(self) -> PostTurnService:
        """Build post-turn service for persistence and background tasks."""
        return PostTurnService(
            storage=self.storage,
            memory_service=self.memory_service,
        )

    def _get_post_turn_service(self) -> PostTurnService:
        """Lazily initialize post-turn service for tests using __new__."""
        service = getattr(self, "post_turn_service", None)
        if service is None:
            service = self._create_post_turn_service()
            self.post_turn_service = service
        return service

    def _create_context_assembly_service(self) -> ContextAssemblyService:
        """Build context assembly service for single/compare flows."""
        return ContextAssemblyService(
            storage=self.storage,
            memory_service=self.memory_service,
            webpage_service=self.webpage_service,
            search_service=self.search_service,
            source_context_service=self.source_context_service,
            rag_config_service=self.rag_config_service,
            rag_context_builder=self._build_rag_context_and_sources,
        )

    def _get_context_assembly_service(self) -> ContextAssemblyService:
        """Lazily initialize context assembly service for tests using __new__."""
        service = getattr(self, "context_assembly_service", None)
        if service is None:
            service = self._create_context_assembly_service()
            self.context_assembly_service = service
        return service

    def _get_file_reference_config(self) -> FileReferenceConfig:
        """Load latest runtime limits; fall back to hardcoded defaults on error."""
        try:
            self.file_reference_config_service.reload_config()
            return self.file_reference_config_service.config
        except Exception as e:
            logger.warning("Failed to refresh file reference config, using defaults: %s", e)
            return FileReferenceConfig(
                ui_preview_max_chars=1200,
                ui_preview_max_lines=28,
                injection_preview_max_chars=self._FILE_CONTEXT_PREVIEW_CHARS,
                injection_preview_max_lines=self._FILE_CONTEXT_PREVIEW_LINES,
                chunk_size=self._FILE_CONTEXT_CHUNK_SIZE,
                max_chunks=self._FILE_CONTEXT_MAX_CHUNKS,
                total_budget_chars=self._FILE_CONTEXT_TOTAL_BUDGET_CHARS,
            )

    @staticmethod
    def _format_file_reference_block(title: str, body: str) -> str:
        """Wrap file reference context in the same block format used by frontend blocks."""
        return f"[Block: {title}]\n```text\n{body}\n```"

    @staticmethod
    def _abbreviate_chunk_text(text: str, max_chars: int, max_lines: int) -> str:
        """Return a compact preview bounded by lines and chars."""
        safe_max_chars = max(1, max_chars)
        safe_max_lines = max(1, max_lines)
        lines = text.splitlines()
        if len(lines) > safe_max_lines:
            text = "\n".join(lines[:safe_max_lines])

        if len(text) <= safe_max_chars:
            return text
        head = int(safe_max_chars * 0.65)
        tail = safe_max_chars - head
        return f"{text[:head]}\n...\n{text[-tail:]}"

    @staticmethod
    def _select_chunk_indexes(total_chunks: int, max_chunks: int) -> List[int]:
        """Select representative chunk indexes across the whole file."""
        if total_chunks <= max_chunks:
            return list(range(total_chunks))
        if max_chunks <= 1:
            return [0]

        selected = {0, total_chunks - 1}
        middle_slots = max_chunks - 2
        if middle_slots > 0:
            for i in range(1, middle_slots + 1):
                idx = round(i * (total_chunks - 1) / (middle_slots + 1))
                selected.add(idx)

        ordered = sorted(selected)
        while len(ordered) > max_chunks:
            ordered.pop(len(ordered) // 2)
        return ordered

    async def _read_file_reference(
        self,
        project_id: str,
        file_path: str,
        cfg: FileReferenceConfig,
    ) -> str:
        """Read file and return chunked, abbreviated context (safe for large files)."""
        try:
            from ..routers.projects import get_project_service
            service = get_project_service()

            # Use existing read_file method
            file_content = await service.read_file(project_id, file_path)
            content = file_content.content or ""

            # Empty file guard
            if not content:
                return self._format_file_reference_block(
                    f"File Reference: {file_path}",
                    "[Content Summary] empty file",
                )

            chunk_size = max(1, cfg.chunk_size)
            max_chunks = max(1, cfg.max_chunks)
            preview_max_chars = max(1, cfg.injection_preview_max_chars)
            preview_max_lines = max(1, cfg.injection_preview_max_lines)

            chunks = [
                content[i:i + chunk_size]
                for i in range(0, len(content), chunk_size)
            ]
            total_chunks = len(chunks)
            selected_indexes = self._select_chunk_indexes(total_chunks, max_chunks)

            chunk_blocks: List[str] = []
            for idx in selected_indexes:
                chunk = chunks[idx]
                start_char = idx * chunk_size + 1
                end_char = min((idx + 1) * chunk_size, len(content))
                preview = self._abbreviate_chunk_text(
                    chunk,
                    preview_max_chars,
                    preview_max_lines,
                )
                chunk_blocks.append(
                    f"[Chunk {idx + 1}/{total_chunks} | chars {start_char}-{end_char}]\n{preview}"
                )
            block_body = (
                f"[Content Summary] {len(content)} chars, {total_chunks} chunks; "
                f"showing {len(selected_indexes)} abbreviated chunks "
                f"(<= {preview_max_lines} lines and <= {preview_max_chars} chars each).\n\n"
                f"{chr(10).join(chunk_blocks)}\n\n"
                "[Hint] Ask for a specific chunk number or keyword range if you need more detail."
            )
            return self._format_file_reference_block(f"File Reference: {file_path}", block_body)
        except Exception as e:
            logger.warning(f"Failed to read file {file_path} from project {project_id}: {e}")
            return self._format_file_reference_block(
                f"File Reference: {file_path}",
                "[Error] Could not read file",
            )

    async def _build_file_context_block(
        self,
        file_references: Optional[List[Dict[str, str]]]
    ) -> str:
        """Build bounded context from referenced files to avoid context explosion."""
        if not file_references:
            return ""

        cfg = self._get_file_reference_config()
        total_budget_chars = max(1, cfg.total_budget_chars)
        parts: List[str] = []
        used_chars = 0

        for index, ref in enumerate(file_references):
            ref_project_id = ref.get("project_id")
            ref_path = ref.get("path")
            if not ref_project_id or not ref_path:
                continue
            file_context = await self._read_file_reference(
                ref_project_id,
                ref_path,
                cfg,
            )

            if used_chars + len(file_context) > total_budget_chars:
                skipped = len(file_references) - index
                parts.append(
                    self._format_file_reference_block(
                        "File Reference Budget",
                        f"[File Context Truncated] budget reached; skipped {skipped} remaining file reference(s).",
                    )
                )
                break

            parts.append(file_context)
            used_chars += len(file_context)

        return "\n\n".join(parts)

    async def _build_rag_context_and_sources(
        self,
        *,
        raw_user_message: str,
        assistant_id: Optional[str],
        assistant_obj: Optional[AssistantLike] = None,
        runtime_model_id: Optional[str] = None,
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Build RAG context and source metadata for the current assistant."""
        rag_sources: List[Dict[str, Any]] = []
        if not assistant_id or assistant_id.startswith("__legacy_model_"):
            return None, rag_sources

        try:
            assistant_for_rag = assistant_obj
            if assistant_for_rag is None:
                from .assistant_config_service import AssistantConfigService

                assistant_service = AssistantConfigService()
                assistant_for_rag = await assistant_service.get_assistant(assistant_id)

            kb_ids = list(getattr(assistant_for_rag, "knowledge_base_ids", None) or [])
            if not kb_ids:
                return None, rag_sources

            from .rag_service import RagService

            rag_service = RagService()
            rag_results, rag_diagnostics = await rag_service.retrieve_with_diagnostics(
                raw_user_message,
                kb_ids,
                runtime_model_id=runtime_model_id,
            )
            rag_sources.append(rag_service.build_rag_diagnostics_source(rag_diagnostics))
            if not rag_results:
                return None, rag_sources

            rag_context = rag_service.build_rag_context(raw_user_message, rag_results)
            rag_sources.extend([r.to_dict() for r in rag_results])
            return rag_context, rag_sources
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            return None, rag_sources

    @staticmethod
    def _merge_tool_diagnostics_into_sources(
        all_sources: List[Dict[str, Any]],
        tool_diagnostics: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not tool_diagnostics:
            return all_sources

        payload = {
            "tool_search_count": int(tool_diagnostics.get("tool_search_count", 0) or 0),
            "tool_search_unique_count": int(
                tool_diagnostics.get("tool_search_unique_count", 0) or 0
            ),
            "tool_search_duplicate_count": int(
                tool_diagnostics.get("tool_search_duplicate_count", 0) or 0
            ),
            "tool_read_count": int(tool_diagnostics.get("tool_read_count", 0) or 0),
            "tool_finalize_reason": str(
                tool_diagnostics.get("tool_finalize_reason", "normal_no_tools") or "normal_no_tools"
            ),
        }

        diagnostics_source: Optional[Dict[str, Any]] = None
        for source in reversed(all_sources):
            if str(source.get("type", "")) == "rag_diagnostics":
                diagnostics_source = source
                break

        should_create_new = (
            payload["tool_search_count"] > 0
            or payload["tool_read_count"] > 0
            or payload["tool_search_duplicate_count"] > 0
            or payload["tool_finalize_reason"] != "normal_no_tools"
        )
        if diagnostics_source is None:
            if not should_create_new:
                return all_sources
            diagnostics_source = {
                "type": "rag_diagnostics",
                "title": "RAG Diagnostics",
                "snippet": "Tool diagnostics",
            }
            all_sources.append(diagnostics_source)

        diagnostics_source.update(payload)
        tool_snippet = (
            f"tool s:{payload['tool_search_count']} "
            f"u:{payload['tool_search_unique_count']} "
            f"d:{payload['tool_search_duplicate_count']} "
            f"r:{payload['tool_read_count']} "
            f"f:{payload['tool_finalize_reason']}"
        )
        existing_snippet = str(diagnostics_source.get("snippet", "") or "").strip()
        diagnostics_source["snippet"] = (
            f"{existing_snippet} | {tool_snippet}" if existing_snippet else tool_snippet
        )
        return all_sources

    async def process_message(
        self,
        session_id: str,
        user_message: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Process a user message and return AI response.

        Args:
            session_id: Session UUID
            user_message: User's input text
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")
            use_web_search: Whether to use web search
            search_query: Optional explicit search query
            file_references: List of {path, project_id} for @file references

        Returns:
            AI assistant's response text and sources

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        response_chunks: List[str] = []
        latest_sources: List[Dict[str, Any]] = []

        async for event in self.process_message_stream(
            session_id=session_id,
            user_message=user_message,
            context_type=context_type,
            project_id=project_id,
            use_web_search=use_web_search,
            search_query=search_query,
            file_references=file_references,
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
        session_id: str,
        user_message: str,
        skip_user_append: bool = False,
        reasoning_effort: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None
    ) -> AsyncIterator[Any]:
        """Stream process user message and return AI response stream.

        Args:
            session_id: Session UUID
            user_message: User's input text
            skip_user_append: Whether to skip appending user message (for regeneration)
            reasoning_effort: Reasoning effort level: "low", "medium", "high"
            attachments: List of file attachments with {filename, size, mime_type, temp_path}
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")
            use_web_search: Whether to use web search
            search_query: Optional explicit search query
            file_references: List of {path, project_id} for @file references

        Yields:
            String tokens during streaming, or dict events:
            - {"type": "usage", "usage": {...}, "cost": {...}} at the end

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        async for event in self._get_single_chat_flow_service().process_message_stream(
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
        ):
            yield event

    async def _prepare_context(
        self,
        session_id: str,
        raw_user_message: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
    ) -> ContextPayload:
        """Prepare shared context for LLM calls."""
        return await self._get_context_assembly_service().prepare_context(
            session_id=session_id,
            raw_user_message=raw_user_message,
            context_type=context_type,
            project_id=project_id,
            use_web_search=use_web_search,
            search_query=search_query,
        )

    @staticmethod
    def _build_group_identity_prompt(
        current_assistant_id: str,
        current_assistant_name: str,
        group_assistants: List[str],
        assistant_name_map: Dict[str, str],
    ) -> str:
        """Build explicit role and participant instructions for group chat rounds."""
        participants: List[str] = []
        for index, participant_id in enumerate(group_assistants, start=1):
            participant_name = assistant_name_map.get(participant_id, participant_id)
            marker = " (you)" if participant_id == current_assistant_id else ""
            participants.append(f"{index}. {participant_name} [{participant_id}]{marker}")

        participants_block = "\n".join(participants) if participants else "unknown"
        return (
            "Group chat identity:\n"
            f"You are {current_assistant_name} [{current_assistant_id}] in a multi-assistant discussion.\n"
            "Participants and speaking order:\n"
            f"{participants_block}\n\n"
            "Role rules:\n"
            "- Do not claim other assistants' statements as your own.\n"
            "- When responding, continue from your own perspective and style.\n"
            "- Never output internal role labels or metadata markers to the user."
        )

    @staticmethod
    def _build_group_history_hint(
        messages: List[Dict[str, Any]],
        current_assistant_id: str,
        assistant_name_map: Dict[str, str],
        max_turns: int = 12,
    ) -> str:
        """Build a compact speaker-labeled assistant turn summary for disambiguation."""
        turn_lines: List[str] = []
        for message in messages:
            if message.get("role") != "assistant":
                continue

            speaker_id = message.get("assistant_id")
            if not speaker_id:
                continue

            speaker_name = assistant_name_map.get(speaker_id, speaker_id)
            ownership = "self" if speaker_id == current_assistant_id else "other"
            content = (message.get("content") or "").replace("\n", " ").strip()
            if len(content) > 120:
                content = f"{content[:120]}..."
            turn_lines.append(f"- {speaker_name} ({ownership}): {content}")

        if not turn_lines:
            return ""

        recent_lines = turn_lines[-max_turns:]
        return (
            "Assistant turn history:\n"
            "Use this speaker mapping to distinguish your own prior replies from other assistants:\n"
            f"{chr(10).join(recent_lines)}\n"
            "These labels are internal guidance only; do not output them verbatim."
        )

    @staticmethod
    def _assistant_params_from_config(assistant_obj: AssistantLike) -> Dict[str, Any]:
        """Extract generation params from assistant config object."""
        return {
            "temperature": assistant_obj.temperature,
            "max_tokens": assistant_obj.max_tokens,
            "top_p": assistant_obj.top_p,
            "top_k": assistant_obj.top_k,
            "frequency_penalty": assistant_obj.frequency_penalty,
            "presence_penalty": assistant_obj.presence_penalty,
        }

    @staticmethod
    def _resolve_compare_model_name(model_id: str) -> str:
        """Resolve best-effort display name for compare stream model events."""
        try:
            from .model_config_service import ModelConfigService

            model_service = ModelConfigService()
            parts = model_id.split(":", 1)
            simple_id = parts[1] if len(parts) > 1 else model_id
            model_cfg, _ = model_service.get_model_and_provider_sync(model_id)
            return getattr(model_cfg, "name", simple_id) if model_cfg else simple_id
        except Exception:
            return model_id

    @staticmethod
    def _extract_model_template_params(model_obj: Any) -> Dict[str, Any]:
        """Extract per-model chat template params for runtime participant creation."""
        template = getattr(model_obj, "chat_template", None)
        if not template:
            return {}
        if hasattr(template, "model_dump"):
            raw_template = template.model_dump(exclude_none=True)
        elif isinstance(template, dict):
            raw_template = {k: v for k, v in template.items() if v is not None}
        else:
            return {}
        return {
            "temperature": raw_template.get("temperature"),
            "max_tokens": raw_template.get("max_tokens"),
            "top_p": raw_template.get("top_p"),
            "top_k": raw_template.get("top_k"),
            "frequency_penalty": raw_template.get("frequency_penalty"),
            "presence_penalty": raw_template.get("presence_penalty"),
        }

    async def _build_group_runtime_assistant(
        self,
        participant_token: str,
    ) -> Optional[Tuple[str, AssistantLike, str]]:
        """Resolve assistant/model participant token to runtime assistant object."""
        try:
            participant = parse_group_participant(participant_token)
        except ValueError:
            return None

        if participant.kind == "assistant":
            from .assistant_config_service import AssistantConfigService

            assistant_service = AssistantConfigService()
            assistant_obj = await assistant_service.get_assistant(participant.value)
            if not assistant_obj or not assistant_obj.enabled:
                return None
            return participant.token, assistant_obj, assistant_obj.name

        from .model_config_service import ModelConfigService

        model_service = ModelConfigService()
        model_obj = await model_service.get_model(participant.value)
        if not model_obj or not model_obj.enabled:
            return None

        composite_model_id = f"{model_obj.provider_id}:{model_obj.id}"
        template_params = self._extract_model_template_params(model_obj)
        runtime_assistant = _RuntimeAssistant(
            id=participant.token,
            name=model_obj.name or model_obj.id,
            icon="CpuChip",
            description=f"Direct model participant: {composite_model_id}",
            model_id=composite_model_id,
            system_prompt=None,
            temperature=template_params.get("temperature", 0.7),
            max_tokens=template_params.get("max_tokens"),
            top_p=template_params.get("top_p"),
            top_k=template_params.get("top_k"),
            frequency_penalty=template_params.get("frequency_penalty"),
            presence_penalty=template_params.get("presence_penalty"),
            max_rounds=None,
            memory_enabled=False,
            knowledge_base_ids=[],
            enabled=True,
        )
        return participant.token, runtime_assistant, runtime_assistant.name

    @staticmethod
    def _resolve_group_round_limit(raw_limit: Optional[int], *, fallback: int = 3, hard_cap: int = 6) -> int:
        """Normalize assistant max_rounds for committee orchestration loops."""
        return CommitteePolicy.resolve_group_round_limit(
            raw_limit,
            fallback=fallback,
            hard_cap=hard_cap,
        )

    @staticmethod
    def _resolve_committee_round_policy(
        raw_limit: Optional[int],
        *,
        participant_count: int,
    ) -> Dict[str, int]:
        """Derive round/depth policy for committee mode to avoid premature convergence."""
        return CommitteePolicy.resolve_committee_round_policy(
            raw_limit,
            participant_count=participant_count,
        )

    def _resolve_group_settings(
        self,
        *,
        group_mode: Optional[str],
        group_assistants: List[str],
        group_settings: Optional[Dict[str, Any]],
        assistant_config_map: Dict[str, AssistantLike],
    ):
        """Resolve runtime group settings with backward-compatible defaults."""
        return GroupSettingsResolver.resolve(
            group_mode=group_mode,
            group_assistants=group_assistants,
            group_settings=group_settings,
            assistant_config_map=assistant_config_map,
            resolve_round_policy=self._resolve_committee_round_policy,
        )

    @staticmethod
    def _build_group_instruction_prompt(
        instruction: Optional[str],
        structured_packet: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Wrap internal directives; optionally attach structured committee turn packet."""
        if not instruction and not structured_packet:
            return None

        sections: List[str] = []
        if instruction:
            cleaned = instruction.strip()
            if cleaned:
                sections.append(
                    "Committee instruction:\n"
                    f"{cleaned}\n\n"
                    "Follow this instruction while keeping role consistency and factual grounding."
                )
        if structured_packet:
            try:
                payload = json.dumps(structured_packet, ensure_ascii=True, default=str)
            except Exception:
                payload = str(structured_packet)
            sections.append(
                "Committee turn packet (JSON):\n"
                f"```json\n{payload}\n```\n\n"
                "Use this packet for planning and role consistency. "
                "Do not output JSON unless the user explicitly asks for it."
            )

        if not sections:
            return None
        return "\n\n".join(sections)

    @staticmethod
    def _extract_bullet_items(text: str, *, limit: int = 5) -> List[str]:
        """Extract concise bullet-like items from free-form text."""
        return CommitteeTurnExecutor.extract_bullet_items(text, limit=limit)

    @staticmethod
    def _extract_keyword_sentences(
        text: str,
        *,
        keywords: List[str],
        limit: int = 4,
    ) -> List[str]:
        """Extract short sentences containing any keyword."""
        return CommitteeTurnExecutor.extract_keyword_sentences(
            text,
            keywords=keywords,
            limit=limit,
        )

    def _build_structured_turn_summary(self, content: str) -> Dict[str, Any]:
        """Build lightweight structured summary from assistant natural-language output."""
        return CommitteeTurnExecutor.build_structured_turn_summary(content)

    def _build_committee_turn_packet(
        self,
        *,
        state: CommitteeRuntimeState,
        target_assistant_id: str,
        assistant_name_map: Dict[str, str],
        instruction: Optional[str],
    ) -> Dict[str, Any]:
        """Build structured per-turn packet used as internal context for committee members."""
        return CommitteeTurnExecutor.build_committee_turn_packet(
            state=state,
            target_assistant_id=target_assistant_id,
            assistant_name_map=assistant_name_map,
            instruction=instruction,
        )

    @staticmethod
    def _normalize_identity_token(value: str) -> str:
        """Normalize identity labels for lightweight role-drift checks."""
        return CommitteeTurnExecutor.normalize_identity_token(value)

    def _detect_group_role_drift(
        self,
        *,
        content: str,
        expected_assistant_id: str,
        expected_assistant_name: str,
        participant_name_map: Dict[str, str],
    ) -> Optional[str]:
        """Detect obvious cases where a speaker claims another participant identity."""
        return CommitteeTurnExecutor.detect_group_role_drift(
            content=content,
            expected_assistant_id=expected_assistant_id,
            expected_assistant_name=expected_assistant_name,
            participant_name_map=participant_name_map,
        )

    @staticmethod
    def _build_role_retry_instruction(
        *,
        base_instruction: Optional[str],
        expected_assistant_name: str,
    ) -> str:
        return CommitteeTurnExecutor.build_role_retry_instruction(
            base_instruction=base_instruction,
            expected_assistant_name=expected_assistant_name,
        )

    async def _get_message_content_by_id(
        self,
        *,
        session_id: str,
        message_id: Optional[str],
        context_type: str,
        project_id: Optional[str],
    ) -> str:
        """Read one message content from session state by message_id."""
        return await self._get_committee_turn_executor().get_message_content_by_id(
            session_id=session_id,
            message_id=message_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def _stream_group_assistant_turn(
        self,
        *,
        session_id: str,
        assistant_id: str,
        assistant_obj: AssistantLike,
        group_assistants: List[str],
        assistant_name_map: Dict[str, str],
        raw_user_message: str,
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[Dict[str, Any]],
        instruction: Optional[str] = None,
        committee_turn_packet: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        trace_round: Optional[int] = None,
        trace_mode: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute one assistant turn in group mode and stream structured events."""
        async for event in self._get_committee_turn_executor().stream_group_assistant_turn(
            session_id=session_id,
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
            group_assistants=group_assistants,
            assistant_name_map=assistant_name_map,
            raw_user_message=raw_user_message,
            reasoning_effort=reasoning_effort,
            context_type=context_type,
            project_id=project_id,
            search_context=search_context,
            search_sources=search_sources,
            instruction=instruction,
            committee_turn_packet=committee_turn_packet,
            trace_id=trace_id,
            trace_round=trace_round,
            trace_mode=trace_mode,
        ):
            yield event

    async def _process_committee_group_message_stream(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        group_assistants: List[str],
        assistant_name_map: Dict[str, str],
        assistant_config_map: Dict[str, AssistantLike],
        group_settings: Optional[Dict[str, Any]],
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[Dict[str, Any]],
        trace_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Committee mode orchestration delegate."""
        async for event in self._get_group_chat_service().process_committee_group_message_stream(
            session_id=session_id,
            raw_user_message=raw_user_message,
            group_assistants=group_assistants,
            assistant_name_map=assistant_name_map,
            assistant_config_map=assistant_config_map,
            group_settings=group_settings,
            reasoning_effort=reasoning_effort,
            context_type=context_type,
            project_id=project_id,
            search_context=search_context,
            search_sources=search_sources,
            trace_id=trace_id,
        ):
            yield event

    async def process_group_message_stream(
        self,
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
        file_references: Optional[List[Dict[str, str]]] = None
    ) -> AsyncIterator[Any]:
        """Stream process user message with multiple assistants (group chat)."""
        async for event in self._get_group_chat_service().process_group_message_stream(
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
        ):
            yield event

    async def process_compare_stream(
        self,
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
        """Stream compare responses from multiple models.

        Yields SSE events tagged by model_id.
        """
        async for event in self._get_compare_flow_service().process_compare_stream(
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
        ):
            yield event
