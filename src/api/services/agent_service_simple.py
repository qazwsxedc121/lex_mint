"""Agent service for processing chat messages - Simplified version (without LangGraph)"""

from typing import Dict, AsyncIterator, Optional, Any, List
from pathlib import Path
import logging
import asyncio

from src.agents.simple_llm import call_llm, call_llm_stream
from src.providers.types import TokenUsage, CostInfo
from .conversation_storage import ConversationStorage
from .pricing_service import PricingService
from .file_service import FileService
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
        logger.info("AgentService initialized (simplified version)")

    async def process_message(self, session_id: str, user_message: str, context_type: str = "chat", project_id: Optional[str] = None) -> str:
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
        print(f"📝 [步骤 1] 保存用户消息到文件...")
        logger.info(f"📝 [步骤 1] 保存用户消息")
        await self.storage.append_message(session_id, "user", user_message, context_type=context_type, project_id=project_id)
        print(f"✅ 用户消息已保存")

        print(f"📂 [步骤 2] 加载会话状态...")
        logger.info(f"📂 [步骤 2] 加载会话状态")
        session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
        messages = session["state"]["messages"]
        model_id = session.get("model_id")  # 获取会话的模型 ID
        print(f"✅ 会话加载完成，当前有 {len(messages)} 条消息，模型: {model_id}")

        print(f"🧠 [步骤 3] 调用 LLM...")
        logger.info(f"🧠 [步骤 3] 调用 LLM")

        # 直接调用 LLM（只调用一次！），传递 model_id
        assistant_message = call_llm(messages, session_id=session_id, model_id=model_id)

        print(f"✅ LLM 处理完成")
        logger.info(f"✅ LLM 处理完成")
        print(f"💬 AI 回复长度: {len(assistant_message)} 字符")

        print(f"📝 [步骤 4] 保存 AI 回复到文件...")
        logger.info(f"📝 [步骤 4] 保存 AI 回复")
        await self.storage.append_message(session_id, "assistant", assistant_message, context_type=context_type, project_id=project_id)
        print(f"✅ AI 回复已保存")

        return assistant_message

    async def process_message_stream(
        self,
        session_id: str,
        user_message: str,
        skip_user_append: bool = False,
        reasoning_effort: str = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None
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

        # Check for legacy session identifier
        if assistant_id and assistant_id.startswith("__legacy_model_"):
            print(f"   Using legacy session mode (model only)")
        elif assistant_id:
            from .assistant_config_service import AssistantConfigService
            assistant_service = AssistantConfigService()
            try:
                assistant = await assistant_service.get_assistant(assistant_id)
                if assistant:
                    system_prompt = assistant.system_prompt
                    max_rounds = assistant.max_rounds
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
                file_service=self.file_service  # Pass file_service for image attachment support
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
            context_type=context_type,
            project_id=project_id
        )
        print(f"[OK] AI response saved with ID: {assistant_message_id}")

        # Trigger title generation in background (do not await)
        try:
            from .title_generation_service import TitleGenerationService
            title_service = TitleGenerationService(storage=self.storage)

            # Reload session to get latest state
            updated_session = await self.storage.get_session(session_id, context_type=context_type, project_id=project_id)
            message_count = len(updated_session['state']['messages'])
            current_title = updated_session['title']

            print(f"[TitleGen] Check: messages={message_count}, title='{current_title}', enabled={title_service.config.enabled}, threshold={title_service.config.trigger_threshold}")

            if title_service.should_generate_title(message_count, current_title):
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
