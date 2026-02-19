"""Agent service for processing chat messages - Simplified version (without LangGraph)"""

from typing import Dict, AsyncIterator, Optional, Any, List, Tuple
import logging
import asyncio
import uuid
import re
import os
import json

from src.agents.simple_llm import call_llm, call_llm_stream, _estimate_total_tokens
from src.providers.types import TokenUsage, CostInfo
from .agent_service_bootstrap import bootstrap_agent_service
from .conversation_storage import ConversationStorage
from .file_reference_config_service import FileReferenceConfig
from .group_orchestration import (
    CommitteeOrchestrator,
    CommitteePolicy,
    GroupSettingsResolver,
    ResolvedCommitteeSettings,
    CommitteeRuntimeState,
    CommitteeTurnExecutor,
)
from .rag_tool_service import RagToolService
from .group_orchestration.log_utils import build_messages_preview_for_log, truncate_log_text

logger = logging.getLogger(__name__)


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
            file_context = await self._read_file_reference(
                ref.get("project_id"),
                ref.get("path"),
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
        assistant_obj: Optional[Any] = None,
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
    def _merge_all_sources(*source_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        for group in source_groups:
            if group:
                merged.extend(group)
        return merged

    def _is_structured_source_context_enabled(self) -> bool:
        try:
            self.rag_config_service.reload_config()
            return bool(
                getattr(
                    self.rag_config_service.config.retrieval,
                    "structured_source_context_enabled",
                    False,
                )
            )
        except Exception as e:
            logger.warning("Failed to read structured source context setting: %s", e)
            return False

    def _append_structured_source_context(
        self,
        *,
        raw_user_message: str,
        system_prompt: Optional[str],
        all_sources: List[Dict[str, Any]],
    ) -> Optional[str]:
        if not all_sources or not self._is_structured_source_context_enabled():
            return system_prompt
        try:
            source_tags = self.source_context_service.build_source_tags(
                query=raw_user_message,
                sources=all_sources,
            )
            if not source_tags:
                return system_prompt
            structured_context = self.source_context_service.apply_template(
                query=raw_user_message,
                source_context=source_tags,
            )
            if not structured_context:
                return system_prompt
            logger.info(
                "[SOURCE_CONTEXT] structured source context injected: source_count=%d",
                len(all_sources),
            )
            return f"{system_prompt}\n\n{structured_context}" if system_prompt else structured_context
        except Exception as e:
            logger.warning("Structured source context injection failed: %s", e)
            return system_prompt

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
        original_user_message = user_message
        file_context_block = await self._build_file_context_block(file_references)
        full_message = f"{file_context_block}\n\n{user_message}" if file_context_block else user_message

        # Keep retrieval/search anchored to user intent instead of expanded file text.
        raw_user_message = original_user_message
        webpage_context = None
        webpage_sources: List[Dict[str, Any]] = []
        try:
            webpage_context, webpage_source_models = await self.webpage_service.build_context(raw_user_message)
            if webpage_source_models:
                webpage_sources = [s.model_dump() for s in webpage_source_models]
        except Exception as e:
            logger.warning(f"Webpage parsing failed: {e}")

        print(f"📝 [步骤 1] 保存用户消息到文件...")
        logger.info(f"📝 [步骤 1] 保存用户消息")
        user_message_id = await self.storage.append_message(
            session_id,
            "user",
            full_message,  # Use full_message with file context
            context_type=context_type,
            project_id=project_id,
        )
        print(f"✅ 用户消息已保存")

        print(f"📂 [步骤 2] 加载会话状态...")
        logger.info(f"📂 [步骤 2] 加载会话状态")
        session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
        messages = session["state"]["messages"]
        model_id = session.get("model_id")  # 获取会话的模型 ID
        assistant_id = session.get("assistant_id")

        # Get assistant config (system prompt)
        system_prompt = None
        assistant_params = {}
        assistant_obj = None
        if assistant_id and not assistant_id.startswith("__legacy_model_"):
            from .assistant_config_service import AssistantConfigService
            assistant_service = AssistantConfigService()
            try:
                assistant = await assistant_service.get_assistant(assistant_id)
                if assistant:
                    assistant_obj = assistant
                    system_prompt = assistant.system_prompt
                    assistant_params = {
                        "temperature": assistant.temperature,
                        "max_tokens": assistant.max_tokens,
                        "top_p": assistant.top_p,
                        "top_k": assistant.top_k,
                        "frequency_penalty": assistant.frequency_penalty,
                        "presence_penalty": assistant.presence_penalty,
                    }
            except Exception as e:
                logger.warning(f"Failed to load assistant config: {e}, using defaults")

        # Apply per-session parameter overrides
        param_overrides = session.get("param_overrides", {})
        if param_overrides:
            if "model_id" in param_overrides:
                model_id = param_overrides["model_id"]
            for key in ["temperature", "max_tokens", "top_p", "top_k", "frequency_penalty", "presence_penalty"]:
                if key in param_overrides:
                    assistant_params[key] = param_overrides[key]

        is_legacy_assistant = bool(assistant_id and assistant_id.startswith("__legacy_model_"))
        assistant_memory_enabled = bool(getattr(assistant_obj, "memory_enabled", True))

        memory_sources: List[Dict[str, Any]] = []
        try:
            include_assistant_memory = bool(
                assistant_id and not is_legacy_assistant and assistant_memory_enabled
            )
            memory_context, memory_sources = self.memory_service.build_memory_context(
                query=raw_user_message,
                assistant_id=assistant_id if include_assistant_memory else None,
                include_global=True,
                include_assistant=include_assistant_memory,
            )
            if memory_context:
                system_prompt = f"{system_prompt}\n\n{memory_context}" if system_prompt else memory_context
        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e}")

        # Optional web page parsing context
        if webpage_context:
            system_prompt = f"{system_prompt}\n\n{webpage_context}" if system_prompt else webpage_context

        # Optional web search
        search_sources: List[Dict[str, Any]] = []
        search_context = None
        if use_web_search:
            query = (search_query or raw_user_message).strip()
            if len(query) > 200:
                query = query[:200]
            try:
                sources = await self.search_service.search(query)
                search_sources = [s.model_dump() for s in sources]
                if sources:
                    search_context = self.search_service.build_search_context(query, sources)
            except Exception as e:
                logger.warning(f"Web search failed: {e}")

        if search_context:
            system_prompt = f"{system_prompt}\n\n{search_context}" if system_prompt else search_context

        # Optional RAG context from knowledge bases
        rag_context, rag_sources = await self._build_rag_context_and_sources(
            raw_user_message=raw_user_message,
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
            runtime_model_id=model_id,
        )
        if rag_context:
            system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context

        all_sources = self._merge_all_sources(
            memory_sources,
            webpage_sources,
            search_sources,
            rag_sources,
        )
        system_prompt = self._append_structured_source_context(
            raw_user_message=raw_user_message,
            system_prompt=system_prompt,
            all_sources=all_sources,
        )

        print(f"[OK] Session loaded, {len(messages)} messages, model: {model_id}")

        print(f"🧠 [步骤 3] 调用 LLM...")
        logger.info(f"🧠 [步骤 3] 调用 LLM")

        # 直接调用 LLM（只调用一次！），传递 model_id
        assistant_message = call_llm(
            messages,
            session_id=session_id,
            model_id=model_id,
            system_prompt=system_prompt,
            **assistant_params
        )

        print(f"✅ LLM 处理完成")
        logger.info(f"✅ LLM 处理完成")
        print(f"💬 AI 回复长度: {len(assistant_message)} 字符")

        print(f"📝 [步骤 4] 保存 AI 回复到文件...")
        logger.info(f"📝 [步骤 4] 保存 AI 回复")

        await self.storage.append_message(
            session_id,
            "assistant",
            assistant_message,
            sources=all_sources if all_sources else None,
            context_type=context_type,
            project_id=project_id
        )
        print(f"✅ AI 回复已保存")

        try:
            asyncio.create_task(
                self.memory_service.extract_and_persist_from_turn(
                    user_message=raw_user_message,
                    assistant_message=assistant_message,
                    assistant_id=assistant_id if not is_legacy_assistant else None,
                    source_session_id=session_id,
                    source_message_id=user_message_id,
                    assistant_memory_enabled=assistant_memory_enabled,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to schedule memory extraction: {e}")

        return assistant_message, all_sources

    async def process_message_stream(
        self,
        session_id: str,
        user_message: str,
        skip_user_append: bool = False,
        reasoning_effort: str = None,
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
        original_user_message = user_message
        file_context_block = await self._build_file_context_block(file_references)
        if file_context_block:
            user_message = f"{file_context_block}\n\n{user_message}"

        # Keep retrieval/search anchored to user intent instead of expanded file text.
        raw_user_message = original_user_message
        webpage_context = None
        webpage_sources: List[Dict[str, Any]] = []
        try:
            webpage_context, webpage_source_models = await self.webpage_service.build_context(raw_user_message)
            if webpage_source_models:
                webpage_sources = [s.model_dump() for s in webpage_source_models]
        except Exception as e:
            logger.warning(f"Webpage parsing failed: {e}")

        # Process attachments
        attachment_metadata = []
        full_message_content = user_message

        if attachments:
            print(f"[Attachments] Processing {len(attachments)} file(s)...")
            logger.info(f"Processing {len(attachments)} file attachments")

            # Get current message count for indexing
            session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
            message_index = len(session["state"]["messages"])

            for idx, att in enumerate(attachments):
                filename = att["filename"]
                temp_path = att["temp_path"]
                mime_type = att["mime_type"]

                # Determine if this is an image file
                is_image = mime_type.startswith("image/")

                # Add metadata for storage
                attachment_metadata.append({
                    "filename": filename,
                    "size": att["size"],
                    "mime_type": mime_type
                })

                if is_image:
                    # Image files: do not embed in text, only store metadata
                    # Content will be read and Base64 encoded in simple_llm.py
                    print(f"   File {idx + 1}: {filename} ({att['size']} bytes) [image]")
                else:
                    # Text files: read and embed content into message
                    temp_file_path = self.file_service.attachments_dir / temp_path
                    content = await self.file_service.get_file_content(temp_file_path)
                    full_message_content += f"\n\n[File {idx + 1}: {filename}]\n{content}\n[End of file]"
                    print(f"   File {idx + 1}: {filename} ({att['size']} bytes) [text]")

                # Move to permanent location
                await self.file_service.move_to_permanent(
                    session_id, message_index, temp_path, filename
                )
                logger.info(f"Moved {filename} to permanent storage")

        # Only append user message when skip_user_append=False
        user_message_id = None
        if not skip_user_append:
            print(f"[Step 1] Saving user message to file...")
            logger.info(f"[Step 1] Saving user message")
            user_message_id = await self.storage.append_message(
                session_id, "user", full_message_content,
                attachments=attachment_metadata if attachment_metadata else None,
                context_type=context_type,
                project_id=project_id
            )
            print(f"[OK] User message saved with ID: {user_message_id}")

            # Immediately yield user message ID so frontend can update UI
            yield {
                "type": "user_message_id",
                "message_id": user_message_id
            }
        else:
            print(f"[Step 1] Skipping user message save (regeneration mode)")
            logger.info(f"[Step 1] Skipping user message save")

        print(f"[Step 2] Loading session state...")
        logger.info(f"[Step 2] Loading session state")
        session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
        messages = session["state"]["messages"]
        assistant_id = session.get("assistant_id")
        model_id = session.get("model_id")
        print(f"[OK] Session loaded, {len(messages)} messages")
        print(f"   Assistant: {assistant_id}, Model: {model_id}")

        # Get assistant config (system prompt and max rounds)
        system_prompt = None
        max_rounds = None
        assistant_params = {}
        assistant_obj = None

        # Check for legacy session identifier
        if assistant_id and assistant_id.startswith("__legacy_model_"):
            print(f"   Using legacy session mode (model only)")
        elif assistant_id:
            from .assistant_config_service import AssistantConfigService
            assistant_service = AssistantConfigService()
            try:
                assistant = await assistant_service.get_assistant(assistant_id)
                if assistant:
                    assistant_obj = assistant
                    system_prompt = assistant.system_prompt
                    max_rounds = assistant.max_rounds
                    assistant_params = {
                        "temperature": assistant.temperature,
                        "max_tokens": assistant.max_tokens,
                        "top_p": assistant.top_p,
                        "top_k": assistant.top_k,
                        "frequency_penalty": assistant.frequency_penalty,
                        "presence_penalty": assistant.presence_penalty,
                    }
                    print(f"   Using assistant config:")
                    if system_prompt:
                        print(f"     - System prompt: {system_prompt[:50]}...")
                    if max_rounds:
                        if max_rounds == -1:
                            print(f"     - Round limit: unlimited")
                        else:
                            print(f"     - Max rounds: {max_rounds}")
            except Exception as e:
                logger.warning(f"   Failed to load assistant config: {e}, using defaults")

        # Apply per-session parameter overrides
        param_overrides = session.get("param_overrides", {})
        if param_overrides:
            if "model_id" in param_overrides:
                model_id = param_overrides["model_id"]
            if "max_rounds" in param_overrides:
                max_rounds = param_overrides["max_rounds"]
            for key in ["temperature", "max_tokens", "top_p", "top_k", "frequency_penalty", "presence_penalty"]:
                if key in param_overrides:
                    assistant_params[key] = param_overrides[key]
            print(f"   Applied param overrides: {param_overrides}")

        is_legacy_assistant = bool(assistant_id and assistant_id.startswith("__legacy_model_"))
        assistant_memory_enabled = bool(getattr(assistant_obj, "memory_enabled", True))

        memory_sources: List[Dict[str, Any]] = []
        try:
            include_assistant_memory = bool(
                assistant_id and not is_legacy_assistant and assistant_memory_enabled
            )
            memory_context, memory_sources = self.memory_service.build_memory_context(
                query=raw_user_message,
                assistant_id=assistant_id if include_assistant_memory else None,
                include_global=True,
                include_assistant=include_assistant_memory,
            )
            if memory_context:
                system_prompt = f"{system_prompt}\n\n{memory_context}" if system_prompt else memory_context
        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e}")

        # Optional web page parsing context
        if webpage_context:
            system_prompt = f"{system_prompt}\n\n{webpage_context}" if system_prompt else webpage_context

        # Optional web search
        search_sources: List[Dict[str, Any]] = []
        search_context = None
        if use_web_search:
            query = (search_query or raw_user_message).strip()
            if len(query) > 200:
                query = query[:200]
            try:
                sources = await self.search_service.search(query)
                search_sources = [s.model_dump() for s in sources]
                if sources:
                    search_context = self.search_service.build_search_context(query, sources)
            except Exception as e:
                logger.warning(f"Web search failed: {e}")

        if search_context:
            system_prompt = f"{system_prompt}\n\n{search_context}" if system_prompt else search_context

        # Optional RAG context from knowledge bases
        rag_context, rag_sources = await self._build_rag_context_and_sources(
            raw_user_message=raw_user_message,
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
            runtime_model_id=model_id,
        )
        if rag_context:
            system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context

        all_sources = self._merge_all_sources(
            memory_sources,
            webpage_sources,
            search_sources,
            rag_sources,
        )
        system_prompt = self._append_structured_source_context(
            raw_user_message=raw_user_message,
            system_prompt=system_prompt,
            all_sources=all_sources,
        )
        if all_sources:
            yield {
                "type": "sources",
                "sources": all_sources
            }

        # === Auto-compression check ===
        try:
            from .compression_config_service import CompressionConfigService
            compression_config_svc = CompressionConfigService()
            comp_config = compression_config_svc.config

            if comp_config.auto_compress_enabled:
                from .model_config_service import ModelConfigService
                model_service = ModelConfigService()
                model_cfg, provider_cfg = model_service.get_model_and_provider_sync(model_id)

                context_length = (
                    getattr(model_cfg.capabilities, 'context_length', None)
                    or getattr(provider_cfg.default_capabilities, 'context_length', None)
                    or 64000
                )
                threshold_tokens = int(context_length * comp_config.auto_compress_threshold)
                estimated_tokens = _estimate_total_tokens(messages)

                if estimated_tokens > threshold_tokens:
                    print(f"[AUTO-COMPRESS] Token estimate {estimated_tokens} > threshold {threshold_tokens}, compressing...")
                    logger.info(f"Auto-compression triggered: {estimated_tokens} tokens > {threshold_tokens} threshold")

                    from .compression_service import CompressionService
                    compression_service = CompressionService(self.storage)
                    result = await compression_service.compress_context(
                        session_id=session_id,
                        context_type=context_type,
                        project_id=project_id,
                    )

                    if result:
                        compress_msg_id, compressed_count = result
                        # Reload messages after compression
                        session = await self.storage.get_session(
                            session_id, context_type=context_type, project_id=project_id
                        )
                        messages = session["state"]["messages"]
                        yield {
                            "type": "auto_compressed",
                            "compressed_count": compressed_count,
                            "message_id": compress_msg_id,
                        }
                        print(f"[AUTO-COMPRESS] Done, compressed {compressed_count} messages")
                    else:
                        print(f"[AUTO-COMPRESS] Compression returned no result, continuing without compression")
        except Exception as e:
            # Auto-compression failure should not block the LLM call
            print(f"[AUTO-COMPRESS] Error (non-fatal): {str(e)}")
            logger.warning(f"Auto-compression failed (non-fatal): {str(e)}", exc_info=True)

        print(f"[Step 3] Streaming LLM call...")
        logger.info(f"[Step 3] Streaming LLM call")

        # Resolve tools if model supports function calling
        llm_tools = None
        rag_tool_executor = None
        try:
            from .model_config_service import ModelConfigService
            model_service = ModelConfigService()
            model_cfg, provider_cfg = model_service.get_model_and_provider_sync(model_id)
            merged_caps = model_service.get_merged_capabilities(model_cfg, provider_cfg)
            if merged_caps.function_calling:
                from src.tools.registry import get_tool_registry
                llm_tools = list(get_tool_registry().get_all_tools())
                kb_ids_for_tools = list(getattr(assistant_obj, "knowledge_base_ids", None) or [])
                if assistant_id and not is_legacy_assistant and kb_ids_for_tools:
                    rag_tool_service = RagToolService(
                        assistant_id=assistant_id,
                        allowed_kb_ids=kb_ids_for_tools,
                        runtime_model_id=model_id,
                    )
                    rag_tools = rag_tool_service.get_tools()
                    if rag_tools:
                        llm_tools.extend(rag_tools)
                        rag_tool_executor = rag_tool_service.execute_tool
                        print(
                            f"[TOOLS] Added RAG tools for assistant {assistant_id}: "
                            f"{len(rag_tools)} tools, kb_count={len(kb_ids_for_tools)}"
                        )
                print(f"[TOOLS] Function calling enabled, {len(llm_tools)} tools available")
        except Exception as e:
            logger.warning(f"Failed to resolve tools: {e}")

        # Collect full response for saving
        full_response = ""
        usage_data: Optional[TokenUsage] = None
        cost_data: Optional[CostInfo] = None

        try:
            # Stream LLM, pass model_id, system_prompt, max_rounds, reasoning_effort, file_service, tools
            async for chunk in call_llm_stream(
                messages,
                session_id=session_id,
                model_id=model_id,
                system_prompt=system_prompt,
                max_rounds=max_rounds,
                reasoning_effort=reasoning_effort,
                file_service=self.file_service,  # Pass file_service for image attachment support
                tools=llm_tools,
                tool_executor=rag_tool_executor,
                **assistant_params
            ):
                # Check if this is a usage data dict
                if isinstance(chunk, dict) and chunk.get("type") == "usage":
                    usage_data = chunk["usage"]
                    # Calculate cost
                    if model_id and usage_data:
                        parts = model_id.split(":", 1)
                        provider_id = parts[0] if len(parts) > 1 else ""
                        simple_model_id = parts[1] if len(parts) > 1 else model_id
                        cost_data = self.pricing_service.calculate_cost(
                            provider_id, simple_model_id, usage_data
                        )
                    continue

                # Forward context_info event to frontend
                if isinstance(chunk, dict) and chunk.get("type") == "context_info":
                    yield chunk
                    continue

                # Forward thinking_duration event to frontend
                if isinstance(chunk, dict) and chunk.get("type") == "thinking_duration":
                    yield chunk
                    continue

                # Forward tool_calls and tool_results events to frontend
                if isinstance(chunk, dict) and chunk.get("type") in ("tool_calls", "tool_results"):
                    yield chunk
                    continue

                full_response += chunk
                yield chunk

            print(f"[OK] LLM streaming complete")
            logger.info(f"[OK] LLM streaming complete")
            print(f"[MSG] AI response length: {len(full_response)} chars")

        except asyncio.CancelledError:
            print(f"[WARN] Stream generation cancelled, saving partial content...")
            logger.warning(f"Stream generation cancelled, saving partial content ({len(full_response)} chars)")
            if full_response:
                await self.storage.append_message(
                    session_id, "assistant", full_response,
                    context_type=context_type,
                    project_id=project_id
                )
                print(f"[OK] Partial AI response saved")
            raise

        print(f"[Step 4] Saving complete AI response to file...")
        logger.info(f"[Step 4] Saving complete AI response")
        assistant_message_id = await self.storage.append_message(
            session_id, "assistant", full_response,
            usage=usage_data, cost=cost_data,
            sources=all_sources if all_sources else None,
            context_type=context_type,
            project_id=project_id
        )
        print(f"[OK] AI response saved with ID: {assistant_message_id}")

        # Update memory in background. Keep this enabled for regeneration/edit flows
        # (skip_user_append=True) so edited user messages can still refresh memory.
        try:
            if raw_user_message and full_response:
                asyncio.create_task(
                    self.memory_service.extract_and_persist_from_turn(
                        user_message=raw_user_message,
                        assistant_message=full_response,
                        assistant_id=assistant_id if not is_legacy_assistant else None,
                        source_session_id=session_id,
                        source_message_id=user_message_id,
                        assistant_memory_enabled=assistant_memory_enabled,
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to schedule memory extraction: {e}")

        # Trigger title generation in background (do not await)
        # Skip for temporary sessions to save API cost
        is_temporary = session.get("temporary", False)
        try:
            from .title_generation_service import TitleGenerationService
            title_service = TitleGenerationService(storage=self.storage)

            # Reload session to get latest state
            updated_session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
            message_count = len(updated_session['state']['messages'])
            current_title = updated_session['title']

            print(f"[TitleGen] Check: messages={message_count}, title='{current_title}', enabled={title_service.config.enabled}, threshold={title_service.config.trigger_threshold}, temporary={is_temporary}")

            if not is_temporary and title_service.should_generate_title(message_count, current_title):
                # Create background task (do not await)
                asyncio.create_task(title_service.generate_title_async(session_id))
                print(f"[TitleGen] Background title generation task created")
            else:
                print(f"[TitleGen] Skipped: condition not met")
        except Exception as e:
            logger.error(f"[TitleGen] Failed to create title generation task: {e}")
            # Don't raise - title generation failure should not affect main flow

        # Yield usage and cost data as a special event at the end
        if usage_data:
            usage_event = {
                "type": "usage",
                "usage": usage_data.model_dump(),
            }
            if cost_data:
                usage_event["cost"] = cost_data.model_dump()
            yield usage_event

        # Yield assistant message ID so frontend can update UI
        assistant_message_id_event = {
            "type": "assistant_message_id",
            "message_id": assistant_message_id
        }
        yield assistant_message_id_event

        # Generate follow-up questions
        try:
            from .followup_service import FollowupService
            followup_service = FollowupService()

            if followup_service.config.enabled and followup_service.config.count > 0:
                updated_session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
                messages_for_followup = updated_session['state']['messages']
                questions = await followup_service.generate_followups_async(messages_for_followup)
                if questions:
                    yield {"type": "followup_questions", "questions": questions}
        except Exception as e:
            logger.warning(f"Failed to generate follow-up questions: {e}")

    async def _prepare_context(
        self,
        session_id: str,
        raw_user_message: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Prepare shared context for LLM calls.

        Returns a dict with keys: messages, system_prompt, assistant_params,
        all_sources, model_id, assistant_id, is_legacy_assistant, assistant_memory_enabled, max_rounds
        """
        session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
        messages = session["state"]["messages"]
        assistant_id = session.get("assistant_id")
        model_id = session.get("model_id")

        system_prompt = None
        max_rounds = None
        assistant_params = {}
        assistant_obj = None

        if assistant_id and assistant_id.startswith("__legacy_model_"):
            pass
        elif assistant_id:
            from .assistant_config_service import AssistantConfigService
            assistant_service = AssistantConfigService()
            try:
                assistant = await assistant_service.get_assistant(assistant_id)
                if assistant:
                    assistant_obj = assistant
                    system_prompt = assistant.system_prompt
                    max_rounds = assistant.max_rounds
                    assistant_params = {
                        "temperature": assistant.temperature,
                        "max_tokens": assistant.max_tokens,
                        "top_p": assistant.top_p,
                        "top_k": assistant.top_k,
                        "frequency_penalty": assistant.frequency_penalty,
                        "presence_penalty": assistant.presence_penalty,
                    }
            except Exception as e:
                logger.warning(f"Failed to load assistant config: {e}, using defaults")

        param_overrides = session.get("param_overrides", {})
        if param_overrides:
            if "model_id" in param_overrides:
                model_id = param_overrides["model_id"]
            if "max_rounds" in param_overrides:
                max_rounds = param_overrides["max_rounds"]
            for key in ["temperature", "max_tokens", "top_p", "top_k", "frequency_penalty", "presence_penalty"]:
                if key in param_overrides:
                    assistant_params[key] = param_overrides[key]

        is_legacy_assistant = bool(assistant_id and assistant_id.startswith("__legacy_model_"))
        assistant_memory_enabled = bool(getattr(assistant_obj, "memory_enabled", True))

        # Build context: memory, webpage, search, RAG
        memory_sources: List[Dict[str, Any]] = []
        try:
            include_assistant_memory = bool(
                assistant_id and not is_legacy_assistant and assistant_memory_enabled
            )
            memory_context, memory_sources = self.memory_service.build_memory_context(
                query=raw_user_message,
                assistant_id=assistant_id if include_assistant_memory else None,
                include_global=True,
                include_assistant=include_assistant_memory,
            )
            if memory_context:
                system_prompt = f"{system_prompt}\n\n{memory_context}" if system_prompt else memory_context
        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e}")

        webpage_sources: List[Dict[str, Any]] = []
        try:
            webpage_context, webpage_source_models = await self.webpage_service.build_context(raw_user_message)
            if webpage_source_models:
                webpage_sources = [s.model_dump() for s in webpage_source_models]
            if webpage_context:
                system_prompt = f"{system_prompt}\n\n{webpage_context}" if system_prompt else webpage_context
        except Exception as e:
            logger.warning(f"Webpage parsing failed: {e}")

        search_sources: List[Dict[str, Any]] = []
        if use_web_search:
            query = (search_query or raw_user_message).strip()
            if len(query) > 200:
                query = query[:200]
            try:
                sources = await self.search_service.search(query)
                search_sources = [s.model_dump() for s in sources]
                if sources:
                    search_context = self.search_service.build_search_context(query, sources)
                    if search_context:
                        system_prompt = f"{system_prompt}\n\n{search_context}" if system_prompt else search_context
            except Exception as e:
                logger.warning(f"Web search failed: {e}")

        rag_context, rag_sources = await self._build_rag_context_and_sources(
            raw_user_message=raw_user_message,
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
            runtime_model_id=model_id,
        )
        if rag_context:
            system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context

        all_sources = self._merge_all_sources(
            memory_sources,
            webpage_sources,
            search_sources,
            rag_sources,
        )
        system_prompt = self._append_structured_source_context(
            raw_user_message=raw_user_message,
            system_prompt=system_prompt,
            all_sources=all_sources,
        )

        return {
            "messages": messages,
            "system_prompt": system_prompt,
            "assistant_params": assistant_params,
            "all_sources": all_sources,
            "model_id": model_id,
            "assistant_id": assistant_id,
            "is_legacy_assistant": is_legacy_assistant,
            "assistant_memory_enabled": assistant_memory_enabled,
            "max_rounds": max_rounds,
        }

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
    def _assistant_params_from_config(assistant_obj: Any) -> Dict[str, Any]:
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
        assistant_config_map: Dict[str, Any],
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
        assistant_obj: Any,
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
        assistant_config_map: Dict[str, Any],
        group_settings: Optional[Dict[str, Any]],
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[Dict[str, Any]],
        trace_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Committee mode orchestration: supervisor decides who speaks each round."""
        if trace_id is None and self._is_group_trace_enabled():
            trace_id = f"{session_id[:8]}-{uuid.uuid4().hex[:6]}"

        resolved_settings = self._resolve_group_settings(
            group_mode="committee",
            group_assistants=group_assistants,
            group_settings=group_settings,
            assistant_config_map=assistant_config_map,
        )
        committee_settings: Optional[ResolvedCommitteeSettings] = resolved_settings.committee
        if committee_settings is None:
            return

        orchestrator = self._create_committee_orchestrator()
        async for event in orchestrator.process(
            session_id=session_id,
            raw_user_message=raw_user_message,
            group_assistants=group_assistants,
            committee_settings=committee_settings,
            assistant_name_map=assistant_name_map,
            assistant_config_map=assistant_config_map,
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
        reasoning_effort: str = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None
    ) -> AsyncIterator[Any]:
        """Stream process user message with multiple assistants (group chat).

        Supports:
        - round_robin: fixed order speaking
        - committee: supervisor chooses member turns and final synthesis

        Yields:
            - {"type": "user_message_id", "message_id": ...}
            - {"type": "assistant_start", "assistant_id": ..., "name": ..., "icon": ...}
            - String chunks (assistant response text)
            - {"type": "usage", "usage": {...}, "cost": {...}}
            - {"type": "assistant_message_id", "message_id": ...}
            - {"type": "assistant_done", "assistant_id": ...}
            - {"done": True}
        """
        original_user_message = user_message
        file_context_block = await self._build_file_context_block(file_references)
        if file_context_block:
            user_message = f"{file_context_block}\n\n{user_message}"

        raw_user_message = original_user_message

        # Process attachments
        attachment_metadata = []
        full_message_content = user_message

        if attachments:
            session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
            message_index = len(session["state"]["messages"])

            for idx, att in enumerate(attachments):
                filename = att["filename"]
                temp_path = att["temp_path"]
                mime_type = att["mime_type"]
                is_image = mime_type.startswith("image/")

                attachment_metadata.append({
                    "filename": filename,
                    "size": att["size"],
                    "mime_type": mime_type,
                })

                if not is_image:
                    temp_file_path = self.file_service.attachments_dir / temp_path
                    content = await self.file_service.get_file_content(temp_file_path)
                    full_message_content += f"\n\n[File {idx + 1}: {filename}]\n{content}\n[End of file]"

                await self.file_service.move_to_permanent(
                    session_id, message_index, temp_path, filename
                )

        # Append user message
        user_message_id = None
        if not skip_user_append:
            user_message_id = await self.storage.append_message(
                session_id, "user", full_message_content,
                attachments=attachment_metadata if attachment_metadata else None,
                context_type=context_type,
                project_id=project_id
            )
            yield {"type": "user_message_id", "message_id": user_message_id}

        # Load assistant configs
        from .assistant_config_service import AssistantConfigService
        assistant_service = AssistantConfigService()
        assistant_name_map: Dict[str, str] = {}
        assistant_config_map: Dict[str, Any] = {}
        for group_assistant_id in group_assistants:
            assistant_obj = await assistant_service.get_assistant(group_assistant_id)
            if assistant_obj:
                assistant_config_map[group_assistant_id] = assistant_obj
                assistant_name_map[group_assistant_id] = assistant_obj.name

        search_sources: List[Dict[str, Any]] = []
        search_context = None
        if use_web_search:
            query = (search_query or raw_user_message).strip()
            if query:
                try:
                    sources = await self.search_service.search(query)
                    search_sources = [s.model_dump() for s in sources]
                    if sources:
                        search_context = self.search_service.build_search_context(query, sources)
                except Exception as e:
                    logger.warning(f"[GroupChat] Web search failed: {e}")

        normalized_group_mode = (group_mode or "round_robin").strip().lower()
        if normalized_group_mode == "committee":
            trace_id: Optional[str] = None
            if self._is_group_trace_enabled():
                trace_id = f"{session_id[:8]}-{uuid.uuid4().hex[:6]}"
                self._log_group_trace(
                    trace_id,
                    "request",
                    {
                        "session_id": session_id,
                        "group_mode": normalized_group_mode,
                        "group_assistants": group_assistants,
                        "raw_user_message": self._truncate_log_text(
                            raw_user_message, self._GROUP_TRACE_PREVIEW_CHARS
                        ),
                    },
                )
            async for event in self._process_committee_group_message_stream(
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
        else:
            for assistant_id in group_assistants:
                assistant_obj = assistant_config_map.get(assistant_id)
                if not assistant_obj:
                    logger.warning(f"[GroupChat] Assistant '{assistant_id}' not found, skipping")
                    continue
                async for event in self._stream_group_assistant_turn(
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
                ):
                    yield event

        # Title generation (once, after all assistants)
        try:
            from .title_generation_service import TitleGenerationService
            title_service = TitleGenerationService(storage=self.storage)
            updated_session = await self.storage.get_session(
                session_id,
                context_type=context_type,
                project_id=project_id,
            )
            is_temporary = updated_session.get("temporary", False)
            message_count = len(updated_session["state"]["messages"])
            current_title = updated_session["title"]
            if not is_temporary and title_service.should_generate_title(message_count, current_title):
                asyncio.create_task(title_service.generate_title_async(session_id))
        except Exception as e:
            logger.warning(f"[GroupChat] Title generation failed: {e}")

    async def process_compare_stream(
        self,
        session_id: str,
        user_message: str,
        model_ids: List[str],
        reasoning_effort: str = None,
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
        original_user_message = user_message
        file_context_block = await self._build_file_context_block(file_references)
        if file_context_block:
            user_message = f"{file_context_block}\n\n{user_message}"

        # Keep retrieval/search anchored to user intent instead of expanded file text.
        raw_user_message = original_user_message

        # Process attachments (same as process_message_stream)
        attachment_metadata = []
        full_message_content = user_message

        if attachments:
            session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
            message_index = len(session["state"]["messages"])

            for idx, att in enumerate(attachments):
                filename = att["filename"]
                temp_path = att["temp_path"]
                mime_type = att["mime_type"]
                is_image = mime_type.startswith("image/")

                attachment_metadata.append({
                    "filename": filename,
                    "size": att["size"],
                    "mime_type": mime_type,
                })

                if not is_image:
                    temp_file_path = self.file_service.attachments_dir / temp_path
                    content = await self.file_service.get_file_content(temp_file_path)
                    full_message_content += f"\n\n[File {idx + 1}: {filename}]\n{content}\n[End of file]"

                await self.file_service.move_to_permanent(
                    session_id, message_index, temp_path, filename
                )

        # Append user message
        user_message_id = await self.storage.append_message(
            session_id, "user", full_message_content,
            attachments=attachment_metadata if attachment_metadata else None,
            context_type=context_type,
            project_id=project_id,
        )
        yield {"type": "user_message_id", "message_id": user_message_id}

        # Prepare context
        ctx = await self._prepare_context(
            session_id, raw_user_message,
            context_type=context_type, project_id=project_id,
            use_web_search=use_web_search, search_query=search_query,
        )

        if ctx["all_sources"]:
            yield {"type": "sources", "sources": ctx["all_sources"]}

        # Multiplexed streaming from multiple models
        queue: asyncio.Queue = asyncio.Queue()
        model_count = len(model_ids)
        done_count = 0

        async def stream_model(mid: str):
            """Stream a single model's response and put events into queue."""
            full_response = ""
            usage_data = None
            cost_data = None
            try:
                # Get model display name
                try:
                    from .model_config_service import ModelConfigService
                    model_service = ModelConfigService()
                    parts = mid.split(":", 1)
                    simple_id = parts[1] if len(parts) > 1 else mid
                    model_cfg, _ = model_service.get_model_and_provider_sync(mid)
                    model_name = getattr(model_cfg, 'name', simple_id) if model_cfg else simple_id
                except Exception:
                    model_name = mid

                await queue.put({"type": "model_start", "model_id": mid, "model_name": model_name})

                async for chunk in call_llm_stream(
                    ctx["messages"],
                    session_id=session_id,
                    model_id=mid,
                    system_prompt=ctx["system_prompt"],
                    max_rounds=ctx["max_rounds"],
                    reasoning_effort=reasoning_effort,
                    file_service=self.file_service,
                    **ctx["assistant_params"],
                ):
                    if isinstance(chunk, dict) and chunk.get("type") == "usage":
                        usage_data = chunk["usage"]
                        parts = mid.split(":", 1)
                        provider_id = parts[0] if len(parts) > 1 else ""
                        simple_model_id = parts[1] if len(parts) > 1 else mid
                        cost_data = self.pricing_service.calculate_cost(
                            provider_id, simple_model_id, usage_data
                        )
                        continue

                    if isinstance(chunk, dict):
                        # Skip other dict events for comparison
                        continue

                    full_response += chunk
                    await queue.put({"type": "model_chunk", "model_id": mid, "chunk": chunk})

                await queue.put({
                    "type": "model_done",
                    "model_id": mid,
                    "model_name": model_name,
                    "content": full_response,
                    "usage": usage_data.model_dump() if usage_data else None,
                    "cost": cost_data.model_dump() if cost_data else None,
                })
            except Exception as e:
                logger.error(f"Compare model {mid} error: {e}", exc_info=True)
                await queue.put({
                    "type": "model_error",
                    "model_id": mid,
                    "error": str(e),
                })

        # Spawn tasks for all models
        tasks = [asyncio.create_task(stream_model(mid)) for mid in model_ids]

        # Read from queue until all models are done
        model_results = {}
        try:
            while done_count < model_count:
                event = await queue.get()
                yield event

                if event["type"] in ("model_done", "model_error"):
                    done_count += 1
                    mid = event["model_id"]
                    if event["type"] == "model_done":
                        model_results[mid] = {
                            "model_id": mid,
                            "model_name": event.get("model_name", mid),
                            "content": event["content"],
                            "usage": event.get("usage"),
                            "cost": event.get("cost"),
                            "thinking_content": "",
                            "error": None,
                        }
                    else:
                        model_results[mid] = {
                            "model_id": mid,
                            "model_name": mid,
                            "content": "",
                            "usage": None,
                            "cost": None,
                            "thinking_content": "",
                            "error": event.get("error", "Unknown error"),
                        }
        finally:
            # Ensure all tasks complete
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        # Save the first model's response as the normal assistant message
        first_model_id = model_ids[0]
        first_result = model_results.get(first_model_id, {})
        first_content = first_result.get("content", "")
        first_usage = None
        first_cost = None
        if first_result.get("usage"):
            first_usage = TokenUsage(**first_result["usage"])
        if first_result.get("cost"):
            first_cost = CostInfo(**first_result["cost"])

        assistant_message_id = await self.storage.append_message(
            session_id, "assistant", first_content,
            usage=first_usage, cost=first_cost,
            sources=ctx["all_sources"] if ctx["all_sources"] else None,
            context_type=context_type,
            project_id=project_id,
        )

        # Save ALL responses to comparison storage
        responses_list = [model_results[mid] for mid in model_ids if mid in model_results]
        await self.comparison_storage.save(
            session_id, assistant_message_id, responses_list,
            context_type=context_type, project_id=project_id,
        )

        yield {"type": "assistant_message_id", "message_id": assistant_message_id}
