"""Agent service for processing chat messages - Simplified version (without LangGraph)"""

from typing import Dict, AsyncIterator, Optional, Any, List, Tuple
import logging
import asyncio
import uuid

from src.agents.simple_llm import call_llm, call_llm_stream, _estimate_total_tokens
from src.providers.types import TokenUsage, CostInfo
from .conversation_storage import ConversationStorage
from .pricing_service import PricingService
from .comparison_storage import ComparisonStorage
from .file_service import FileService
from .search_service import SearchService
from .webpage_service import WebpageService
from .memory_service import MemoryService
from .file_reference_config_service import FileReferenceConfigService, FileReferenceConfig
from ..config import settings

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
        self.storage = storage
        self.pricing_service = PricingService()
        self.file_service = FileService(settings.attachments_dir, settings.max_file_size_mb)
        self.search_service = SearchService()
        self.webpage_service = WebpageService()
        self.memory_service = MemoryService()
        self.file_reference_config_service = FileReferenceConfigService()
        self.comparison_storage = ComparisonStorage(self.storage)
        logger.info("AgentService initialized (simplified version)")

    _FILE_CONTEXT_CHUNK_SIZE = 2500
    _FILE_CONTEXT_MAX_CHUNKS = 6
    _FILE_CONTEXT_PREVIEW_CHARS = 600
    _FILE_CONTEXT_PREVIEW_LINES = 40
    _FILE_CONTEXT_TOTAL_BUDGET_CHARS = 18000

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
        )
        if rag_context:
            system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context

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
        all_sources: List[Dict[str, Any]] = []
        if memory_sources:
            all_sources.extend(memory_sources)
        if webpage_sources:
            all_sources.extend(webpage_sources)
        if search_sources:
            all_sources.extend(search_sources)
        if rag_sources:
            all_sources.extend(rag_sources)

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
        )
        if rag_context:
            system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context

        all_sources: List[Dict[str, Any]] = []
        if memory_sources:
            all_sources.extend(memory_sources)
        if webpage_sources:
            all_sources.extend(webpage_sources)
        if search_sources:
            all_sources.extend(search_sources)
        if rag_sources:
            all_sources.extend(rag_sources)
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

        # Collect full response for saving
        full_response = ""
        usage_data: Optional[TokenUsage] = None
        cost_data: Optional[CostInfo] = None

        try:
            # Stream LLM, pass model_id, system_prompt, max_rounds, reasoning_effort and file_service
            async for chunk in call_llm_stream(
                messages,
                session_id=session_id,
                model_id=model_id,
                system_prompt=system_prompt,
                max_rounds=max_rounds,
                reasoning_effort=reasoning_effort,
                file_service=self.file_service,  # Pass file_service for image attachment support
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
        )
        if rag_context:
            system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context

        all_sources: List[Dict[str, Any]] = []
        if memory_sources:
            all_sources.extend(memory_sources)
        if webpage_sources:
            all_sources.extend(webpage_sources)
        if search_sources:
            all_sources.extend(search_sources)
        if rag_sources:
            all_sources.extend(rag_sources)

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

    async def process_group_message_stream(
        self,
        session_id: str,
        user_message: str,
        group_assistants: List[str],
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

        Each assistant responds in turn (round-robin), seeing all previous
        responses in the conversation including earlier assistants' replies.

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

        # Process each assistant sequentially
        for assistant_id in group_assistants:
            assistant_obj = assistant_config_map.get(assistant_id)
            if not assistant_obj:
                logger.warning(f"[GroupChat] Assistant '{assistant_id}' not found, skipping")
                continue
            assistant_turn_id = str(uuid.uuid4())

            # Signal assistant start
            yield {
                "type": "assistant_start",
                "assistant_id": assistant_id,
                "assistant_turn_id": assistant_turn_id,
                "name": assistant_obj.name,
                "icon": assistant_obj.icon,
            }

            # Reload session to include previous assistants' responses
            session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
            messages = session["state"]["messages"]
            model_id = assistant_obj.model_id
            history_hint = self._build_group_history_hint(
                messages=messages,
                current_assistant_id=assistant_id,
                assistant_name_map=assistant_name_map,
            )

            # Build per-assistant context
            system_prompt = assistant_obj.system_prompt
            max_rounds = assistant_obj.max_rounds
            assistant_params = {
                "temperature": assistant_obj.temperature,
                "max_tokens": assistant_obj.max_tokens,
                "top_p": assistant_obj.top_p,
                "top_k": assistant_obj.top_k,
                "frequency_penalty": assistant_obj.frequency_penalty,
                "presence_penalty": assistant_obj.presence_penalty,
            }
            identity_prompt = self._build_group_identity_prompt(
                current_assistant_id=assistant_id,
                current_assistant_name=assistant_obj.name,
                group_assistants=group_assistants,
                assistant_name_map=assistant_name_map,
            )
            prompt_parts = [identity_prompt]
            if history_hint:
                prompt_parts.append(history_hint)
            if system_prompt:
                prompt_parts.append(system_prompt)
            system_prompt = "\n\n".join(prompt_parts)

            # Memory context (per-assistant)
            assistant_memory_enabled = bool(getattr(assistant_obj, "memory_enabled", True))
            try:
                memory_context, _ = self.memory_service.build_memory_context(
                    query=raw_user_message,
                    assistant_id=assistant_id,
                    include_global=True,
                    include_assistant=assistant_memory_enabled,
                )
                if memory_context:
                    system_prompt = f"{system_prompt}\n\n{memory_context}" if system_prompt else memory_context
            except Exception as e:
                logger.warning(f"[GroupChat] Memory retrieval failed for {assistant_id}: {e}")

            # RAG context (per-assistant)
            rag_context, _ = await self._build_rag_context_and_sources(
                raw_user_message=raw_user_message,
                assistant_id=assistant_id,
                assistant_obj=assistant_obj,
            )
            if rag_context:
                system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context

            # Stream LLM response
            full_response = ""
            usage_data = None
            cost_data = None

            try:
                async for chunk in call_llm_stream(
                    messages,
                    session_id=session_id,
                    model_id=model_id,
                    system_prompt=system_prompt,
                    max_rounds=max_rounds,
                    reasoning_effort=reasoning_effort,
                    file_service=self.file_service,
                    **assistant_params
                ):
                    if isinstance(chunk, dict) and chunk.get("type") == "usage":
                        usage_data = chunk["usage"]
                        parts = model_id.split(":", 1)
                        provider_id = parts[0] if len(parts) > 1 else ""
                        simple_model_id = parts[1] if len(parts) > 1 else model_id
                        cost_data = self.pricing_service.calculate_cost(
                            provider_id, simple_model_id, usage_data
                        )
                        continue

                    if isinstance(chunk, dict):
                        # Forward context_info, thinking_duration events
                        event = dict(chunk)
                        event["assistant_id"] = assistant_id
                        event["assistant_turn_id"] = assistant_turn_id
                        yield event
                        continue

                    full_response += chunk
                    yield {
                        "type": "assistant_chunk",
                        "assistant_id": assistant_id,
                        "assistant_turn_id": assistant_turn_id,
                        "chunk": chunk,
                    }

            except asyncio.CancelledError:
                if full_response:
                    await self.storage.append_message(
                        session_id, "assistant", full_response,
                        assistant_id=assistant_id,
                        context_type=context_type,
                        project_id=project_id
                    )
                raise

            # Save assistant message with assistant_id metadata
            assistant_message_id = await self.storage.append_message(
                session_id, "assistant", full_response,
                usage=usage_data, cost=cost_data,
                assistant_id=assistant_id,
                context_type=context_type,
                project_id=project_id
            )

            # Yield usage/cost
            if usage_data:
                usage_event = {
                    "type": "usage",
                    "assistant_id": assistant_id,
                    "assistant_turn_id": assistant_turn_id,
                    "usage": usage_data.model_dump(),
                }
                if cost_data:
                    usage_event["cost"] = cost_data.model_dump()
                yield usage_event

            yield {
                "type": "assistant_message_id",
                "assistant_id": assistant_id,
                "assistant_turn_id": assistant_turn_id,
                "message_id": assistant_message_id,
            }
            yield {
                "type": "assistant_done",
                "assistant_id": assistant_id,
                "assistant_turn_id": assistant_turn_id,
            }

        # Title generation (once, after all assistants)
        is_temporary = session.get("temporary", False) if session else False
        try:
            from .title_generation_service import TitleGenerationService
            title_service = TitleGenerationService(storage=self.storage)
            updated_session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
            message_count = len(updated_session['state']['messages'])
            current_title = updated_session['title']
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
