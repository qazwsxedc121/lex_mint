"""
Title Generation Service

Automatically generates conversation titles using a small LLM model.
"""
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

import yaml
from langchain_openai import ChatOpenAI

from .conversation_storage import ConversationStorage
from .model_config_service import ModelConfigService

logger = logging.getLogger(__name__)


@dataclass
class TitleGenerationConfig:
    """Configuration for title generation"""
    enabled: bool
    trigger_threshold: int
    model_id: str
    prompt_template: str
    max_context_rounds: int
    timeout_seconds: int


class TitleGenerationService:
    """Service for automatic title generation"""

    def __init__(self, storage: ConversationStorage, config_path: Optional[str] = None):
        self.storage = storage
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "title_generation_config.yaml"
        else:
            config_path = Path(config_path)

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> TitleGenerationConfig:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            config_data = data.get('title_generation', {})
            return TitleGenerationConfig(
                enabled=config_data.get('enabled', True),
                trigger_threshold=config_data.get('trigger_threshold', 1),
                model_id=config_data.get('model_id', 'openrouter:openai/gpt-4o-mini'),
                prompt_template=config_data.get('prompt_template', ''),
                max_context_rounds=config_data.get('max_context_rounds', 3),
                timeout_seconds=config_data.get('timeout_seconds', 10)
            )
        except Exception as e:
            logger.error(f"Failed to load title generation config: {e}")
            # Return default config
            return TitleGenerationConfig(
                enabled=False,
                trigger_threshold=1,
                model_id='openrouter:openai/gpt-4o-mini',
                prompt_template='',
                max_context_rounds=3,
                timeout_seconds=10
            )

    def reload_config(self):
        """Reload configuration from file"""
        self.config = self._load_config()

    def save_config(self, updates: Dict):
        """Save updated configuration to file"""
        try:
            # Read current config
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # Update fields
            if 'title_generation' not in data:
                data['title_generation'] = {}

            for key, value in updates.items():
                if value is not None:
                    data['title_generation'][key] = value

            # Write back
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

            # Reload
            self.reload_config()
            logger.info("Title generation config updated successfully")
        except Exception as e:
            logger.error(f"Failed to save title generation config: {e}")
            raise

    def should_generate_title(self, message_count: int, current_title: str) -> bool:
        """
        Check if title generation should be triggered

        Args:
            message_count: Total number of messages in the conversation
            current_title: Current session title

        Returns:
            True if title should be generated
        """
        # Check if enabled
        if not self.config.enabled:
            return False

        # Check if title is default or truncated (contains "...")
        # Only generate if title looks like it was auto-truncated
        is_default_title = current_title in ["New Conversation", "New Session", "新对话"]
        is_truncated = "..." in current_title

        if not (is_default_title or is_truncated):
            # Title already looks good, skip generation
            return False

        # Check if threshold is met
        # message_count is total messages, so divide by 2 to get conversation rounds
        conversation_rounds = message_count // 2

        return conversation_rounds >= self.config.trigger_threshold

    async def generate_title_async(self, session_id: str) -> Optional[str]:
        """
        Generate title asynchronously in background

        Args:
            session_id: Session ID to generate title for

        Returns:
            Generated title or None if failed
        """
        try:
            logger.info(f"[TitleGen] Starting title generation for session {session_id}")

            # Load session and messages
            session = await self.storage.get_session(session_id)
            if not session:
                logger.error(f"[TitleGen] Session {session_id} not found")
                return None

            messages = session['state']['messages']
            if not messages:
                logger.error(f"[TitleGen] No messages in session {session_id}")
                return None

            # Extract recent conversation rounds
            max_messages = self.config.max_context_rounds * 2  # user + assistant
            recent_messages = messages[-max_messages:]

            # Build conversation text
            conversation_lines = []
            for msg in recent_messages:
                role = msg.get('type', msg.get('role', 'unknown'))
                content = msg.get('content', '')
                if role == 'human':
                    conversation_lines.append(f"User: {content}")
                elif role == 'assistant':
                    conversation_lines.append(f"Assistant: {content}")

            conversation_text = "\n".join(conversation_lines)

            # Build prompt
            prompt = self.config.prompt_template.format(conversation_text=conversation_text)

            # Initialize model
            model_config_service = ModelConfigService()
            model_instance = model_config_service.get_llm_instance(self.config.model_id)

            # Call model with timeout
            logger.info(f"[TitleGen] Calling model {self.config.model_id}")
            response = await asyncio.wait_for(
                model_instance.ainvoke(prompt),
                timeout=self.config.timeout_seconds
            )

            # Extract and clean title
            title = response.content.strip()

            # Remove quotes if present
            if title.startswith('"') and title.endswith('"'):
                title = title[1:-1]
            if title.startswith("'") and title.endswith("'"):
                title = title[1:-1]

            # Validate length
            if len(title) > 100:
                title = title[:100]

            if not title:
                logger.error("[TitleGen] Generated title is empty")
                return None

            logger.info(f"[TitleGen] Generated title: {title}")

            # Update session metadata
            await self.storage.update_session_metadata(session_id, {'title': title})

            logger.info(f"[TitleGen] Title updated successfully for session {session_id}")
            return title

        except asyncio.TimeoutError:
            logger.error(f"[TitleGen] Timeout generating title for session {session_id}")
            return None
        except Exception as e:
            logger.error(f"[TitleGen] Failed to generate title for session {session_id}: {e}")
            return None
