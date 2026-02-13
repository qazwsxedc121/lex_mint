"""Compression service for summarizing conversation context."""

import asyncio
import logging
import json
from typing import AsyncIterator, Union, Dict, Any, Optional, Tuple

from src.api.services.conversation_storage import ConversationStorage
from src.api.services.model_config_service import ModelConfigService
from src.api.services.compression_config_service import CompressionConfigService
from src.api.services.local_llama_cpp_service import LocalLlamaCppService
from src.api.services.think_tag_filter import ThinkTagStreamFilter, strip_think_blocks
from src.agents.simple_llm import _filter_messages_by_context_boundary

logger = logging.getLogger(__name__)


class CompressionService:
    """Service for compressing conversation context via LLM summarization."""

    def __init__(self, storage: ConversationStorage):
        self.storage = storage
        self.config_service = CompressionConfigService()

    async def compress_context_stream(
        self,
        session_id: str,
        context_type: str = "chat",
        project_id: str = None,
    ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
        """Compress conversation context by summarizing messages via LLM.

        Streams summary tokens, then appends the summary to storage.

        Args:
            session_id: Session UUID
            context_type: Context type ("chat" or "project")
            project_id: Project ID (optional)

        Yields:
            String tokens during streaming, or dict events at the end.
        """
        # Reload config to pick up latest changes
        self.config_service.reload_config()
        config = self.config_service.config

        # Load session
        session = await self.storage.get_session(
            session_id, context_type=context_type, project_id=project_id
        )
        messages = session["state"]["messages"]
        model_id = session.get("model_id")

        # Apply param overrides for model selection
        param_overrides = session.get("param_overrides", {})
        if param_overrides and "model_id" in param_overrides:
            model_id = param_overrides["model_id"]

        # Filter to get only the compressible messages (after last boundary)
        compressible, _ = _filter_messages_by_context_boundary(messages)

        # Check minimum messages
        if len(compressible) < config.min_messages:
            yield {"type": "error", "error": f"Not enough messages to compress (need at least {config.min_messages})"}
            return

        compressed_count = len(compressible)

        # Format messages for summarization
        formatted = self._format_messages(compressible)

        # Build prompt from config template
        prompt = config.prompt_template.format(formatted_messages=formatted)

        # Use compression-specific model if configured, otherwise fall back to session model
        compression_model_id = config.model_id
        if config.provider == "model_config" and compression_model_id:
            model_id = compression_model_id

        if config.provider == "local_gguf":
            try:
                local_llm = LocalLlamaCppService(
                    model_path=config.local_gguf_model_path,
                    n_ctx=config.local_gguf_n_ctx,
                    n_threads=config.local_gguf_n_threads,
                    n_gpu_layers=config.local_gguf_n_gpu_layers,
                )
            except Exception as e:
                yield {"type": "error", "error": str(e)}
                return

            actual_model_id = f"local_gguf:{local_llm.model_path.name}"
            print(f"[COMPRESS] Starting local GGUF compression (model: {actual_model_id})")
            print(f"[COMPRESS] Compressing {compressed_count} messages")
            logger.info(f"Local GGUF compression started: {compressed_count} messages, model: {actual_model_id}")

            try:
                full_response = ""
                think_filter = ThinkTagStreamFilter()
                for token in local_llm.stream_prompt(
                    prompt,
                    temperature=config.temperature,
                    max_tokens=config.local_gguf_max_tokens,
                ):
                    visible = think_filter.feed(token)
                    if visible:
                        full_response += visible
                        yield visible
                        await asyncio.sleep(0)

                tail = think_filter.flush()
                if tail:
                    full_response += tail
                    yield tail
                message_id = await self.storage.append_summary(
                    session_id=session_id,
                    content=full_response,
                    compressed_count=compressed_count,
                    context_type=context_type,
                    project_id=project_id,
                )
                print(f"[COMPRESS] Compression complete: {len(full_response)} chars, message_id: {message_id[:8]}...")
                logger.info(f"Context compression complete: {len(full_response)} chars")
                yield {
                    "type": "compression_complete",
                    "message_id": message_id,
                    "compressed_count": compressed_count,
                }
                return
            except Exception as e:
                print(f"[ERROR] Compression failed: {str(e)}")
                logger.error(f"Compression failed: {str(e)}", exc_info=True)
                yield {"type": "error", "error": str(e)}
                return

        # Get model and adapter
        model_service = ModelConfigService()
        model_config, provider_config = model_service.get_model_and_provider_sync(model_id)

        adapter = model_service.get_adapter_for_provider(provider_config)

        try:
            api_key = model_service.resolve_provider_api_key_sync(provider_config)
        except RuntimeError as e:
            yield {"type": "error", "error": str(e)}
            return

        # Create LLM instance with configured temperature
        llm = adapter.create_llm(
            model=model_config.id,
            base_url=provider_config.base_url,
            api_key=api_key,
            temperature=config.temperature,
            streaming=True,
        )

        actual_model_id = f"{provider_config.id}:{model_config.id}"
        print(f"[COMPRESS] Starting context compression (model: {actual_model_id})")
        print(f"[COMPRESS] Compressing {compressed_count} messages")
        logger.info(f"Context compression started: {compressed_count} messages, model: {actual_model_id}")

        from langchain_core.messages import HumanMessage as HMsg

        langchain_messages = [HMsg(content=prompt)]

        try:
            full_response = ""
            think_filter = ThinkTagStreamFilter()

            async for chunk in adapter.stream(llm, langchain_messages):
                if chunk.content:
                    visible = think_filter.feed(chunk.content)
                    if visible:
                        full_response += visible
                        yield visible

            tail = think_filter.flush()
            if tail:
                full_response += tail
                yield tail

            # Append summary to storage
            message_id = await self.storage.append_summary(
                session_id=session_id,
                content=full_response,
                compressed_count=compressed_count,
                context_type=context_type,
                project_id=project_id,
            )

            print(f"[COMPRESS] Compression complete: {len(full_response)} chars, message_id: {message_id[:8]}...")
            logger.info(f"Context compression complete: {len(full_response)} chars")

            yield {
                "type": "compression_complete",
                "message_id": message_id,
                "compressed_count": compressed_count,
            }

        except Exception as e:
            print(f"[ERROR] Compression failed: {str(e)}")
            logger.error(f"Compression failed: {str(e)}", exc_info=True)
            yield {"type": "error", "error": str(e)}

    def _format_messages(self, messages):
        """Format messages into XML structure for summarization."""
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                parts.append(f"<{role}>{content}</{role}>")
        return "<chat_history>\n" + "\n".join(parts) + "\n</chat_history>"

    async def compress_context(
        self,
        session_id: str,
        context_type: str = "chat",
        project_id: str = None,
    ) -> Optional[Tuple[str, int]]:
        """Non-streaming compression for auto-trigger use.

        Args:
            session_id: Session UUID
            context_type: Context type ("chat" or "project")
            project_id: Project ID (optional)

        Returns:
            Tuple of (message_id, compressed_count) on success, None on failure.
        """
        self.config_service.reload_config()
        config = self.config_service.config

        # Load session
        session = await self.storage.get_session(
            session_id, context_type=context_type, project_id=project_id
        )
        messages = session["state"]["messages"]
        model_id = session.get("model_id")

        param_overrides = session.get("param_overrides", {})
        if param_overrides and "model_id" in param_overrides:
            model_id = param_overrides["model_id"]

        # Filter to get only compressible messages
        compressible, _ = _filter_messages_by_context_boundary(messages)

        if len(compressible) < config.min_messages:
            logger.info(f"[AUTO-COMPRESS] Skipped: only {len(compressible)} messages (need {config.min_messages})")
            return None

        compressed_count = len(compressible)
        formatted = self._format_messages(compressible)
        prompt = config.prompt_template.format(formatted_messages=formatted)

        compression_model_id = config.model_id
        if config.provider == "model_config" and compression_model_id:
            model_id = compression_model_id

        if config.provider == "local_gguf":
            try:
                local_llm = LocalLlamaCppService(
                    model_path=config.local_gguf_model_path,
                    n_ctx=config.local_gguf_n_ctx,
                    n_threads=config.local_gguf_n_threads,
                    n_gpu_layers=config.local_gguf_n_gpu_layers,
                )
                full_response = local_llm.complete_prompt(
                    prompt,
                    temperature=config.temperature,
                    max_tokens=config.local_gguf_max_tokens,
                )
                full_response = strip_think_blocks(full_response)
                message_id = await self.storage.append_summary(
                    session_id=session_id,
                    content=full_response,
                    compressed_count=compressed_count,
                    context_type=context_type,
                    project_id=project_id,
                )
                print(
                    f"[AUTO-COMPRESS] Complete: {len(full_response)} chars, "
                    f"message_id: {message_id[:8]}..."
                )
                logger.info(f"Auto-compression complete: {len(full_response)} chars")
                return message_id, compressed_count
            except Exception as e:
                print(f"[ERROR] Auto-compression failed: {str(e)}")
                logger.error(f"Auto-compression failed: {str(e)}", exc_info=True)
                return None

        model_service = ModelConfigService()
        model_config, provider_config = model_service.get_model_and_provider_sync(model_id)
        adapter = model_service.get_adapter_for_provider(provider_config)

        try:
            api_key = model_service.resolve_provider_api_key_sync(provider_config)
        except RuntimeError as e:
            logger.error(f"[AUTO-COMPRESS] {e}")
            return None

        llm = adapter.create_llm(
            model=model_config.id,
            base_url=provider_config.base_url,
            api_key=api_key,
            temperature=config.temperature,
            streaming=True,
        )

        actual_model_id = f"{provider_config.id}:{model_config.id}"
        print(f"[AUTO-COMPRESS] Starting auto-compression (model: {actual_model_id}, {compressed_count} messages)")
        logger.info(f"Auto-compression started: {compressed_count} messages, model: {actual_model_id}")

        from langchain_core.messages import HumanMessage as HMsg

        langchain_messages = [HMsg(content=prompt)]

        try:
            full_response = ""
            async for chunk in adapter.stream(llm, langchain_messages):
                if chunk.content:
                    full_response += chunk.content
            full_response = strip_think_blocks(full_response)

            message_id = await self.storage.append_summary(
                session_id=session_id,
                content=full_response,
                compressed_count=compressed_count,
                context_type=context_type,
                project_id=project_id,
            )

            print(f"[AUTO-COMPRESS] Complete: {len(full_response)} chars, message_id: {message_id[:8]}...")
            logger.info(f"Auto-compression complete: {len(full_response)} chars")
            return message_id, compressed_count

        except Exception as e:
            print(f"[ERROR] Auto-compression failed: {str(e)}")
            logger.error(f"Auto-compression failed: {str(e)}", exc_info=True)
            return None
