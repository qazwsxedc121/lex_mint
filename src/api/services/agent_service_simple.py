"""Agent service for processing chat messages - Simplified version (without LangGraph)"""

from typing import Dict, AsyncIterator, Optional, Any, List
import logging
import asyncio

from src.agents.simple_llm import call_llm, call_llm_stream, _estimate_total_tokens
from src.providers.types import TokenUsage, CostInfo
from .conversation_storage import ConversationStorage
from .pricing_service import PricingService
from .file_service import FileService
from .search_service import SearchService
from .webpage_service import WebpageService
from .memory_service import MemoryService
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
        logger.info("AgentService initialized (simplified version)")

    async def process_message(
        self,
        session_id: str,
        user_message: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Process a user message and return AI response.

        Args:
            session_id: Session UUID
            user_message: User's input text
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Returns:
            AI assistant's response text

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        raw_user_message = user_message
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
            user_message,
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
        rag_sources: List[Dict[str, Any]] = []
        if assistant_id and not assistant_id.startswith("__legacy_model_"):
            try:
                from .assistant_config_service import AssistantConfigService as _ACS
                from .rag_service import RagService
                _assistant_svc = _ACS()
                _assistant_obj = await _assistant_svc.get_assistant(assistant_id)
                if _assistant_obj and getattr(_assistant_obj, 'knowledge_base_ids', None):
                    rag_service = RagService()
                    rag_results = await rag_service.retrieve(raw_user_message, _assistant_obj.knowledge_base_ids)
                    if rag_results:
                        rag_context = rag_service.build_rag_context(raw_user_message, rag_results)
                        rag_sources = [r.to_dict() for r in rag_results]
                        if rag_context:
                            system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")

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
        search_query: Optional[str] = None
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

        Yields:
            String tokens during streaming, or dict events:
            - {"type": "usage", "usage": {...}, "cost": {...}} at the end

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        raw_user_message = user_message
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
        rag_sources: List[Dict[str, Any]] = []
        if assistant_id and not assistant_id.startswith("__legacy_model_"):
            try:
                from .rag_service import RagService
                # Re-use assistant object if already loaded above
                _rag_assistant = None
                if assistant_id:
                    from .assistant_config_service import AssistantConfigService as _ACS2
                    _rag_svc = _ACS2()
                    _rag_assistant = await _rag_svc.get_assistant(assistant_id)
                if _rag_assistant and getattr(_rag_assistant, 'knowledge_base_ids', None):
                    rag_service = RagService()
                    rag_results = await rag_service.retrieve(raw_user_message, _rag_assistant.knowledge_base_ids)
                    if rag_results:
                        rag_context = rag_service.build_rag_context(raw_user_message, rag_results)
                        rag_sources = [r.to_dict() for r in rag_results]
                        if rag_context:
                            system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")

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

