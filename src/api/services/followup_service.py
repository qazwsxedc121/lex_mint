"""
Follow-up Questions Service

Generates follow-up question suggestions after each chat response.
"""
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

import yaml

from .model_config_service import ModelConfigService

logger = logging.getLogger(__name__)


@dataclass
class FollowupConfig:
    """Configuration for follow-up question generation"""
    enabled: bool
    count: int
    model_id: str
    max_context_rounds: int
    timeout_seconds: int
    prompt_template: str


class FollowupService:
    """Service for generating follow-up question suggestions"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "followup_config.yaml"
        else:
            config_path = Path(config_path)

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> FollowupConfig:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            config_data = data.get('followup', {})
            return FollowupConfig(
                enabled=config_data.get('enabled', True),
                count=config_data.get('count', 3),
                model_id=config_data.get('model_id', 'deepseek:deepseek-chat'),
                max_context_rounds=config_data.get('max_context_rounds', 3),
                timeout_seconds=config_data.get('timeout_seconds', 15),
                prompt_template=config_data.get('prompt_template', '')
            )
        except Exception as e:
            logger.error(f"Failed to load followup config: {e}")
            # Return default config
            return FollowupConfig(
                enabled=False,
                count=3,
                model_id='deepseek:deepseek-chat',
                max_context_rounds=3,
                timeout_seconds=15,
                prompt_template=''
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
            if 'followup' not in data:
                data['followup'] = {}

            for key, value in updates.items():
                if value is not None:
                    data['followup'][key] = value

            # Write back
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

            # Reload
            self.reload_config()
            logger.info("Followup config updated successfully")
        except Exception as e:
            logger.error(f"Failed to save followup config: {e}")
            raise

    async def generate_followups_async(self, messages: List[Dict]) -> List[str]:
        """
        Generate follow-up question suggestions asynchronously

        Args:
            messages: List of conversation messages

        Returns:
            List of follow-up questions
        """
        try:
            if not self.config.enabled or self.config.count <= 0:
                return []

            if not messages:
                logger.warning("[Followup] No messages provided")
                return []

            logger.info(f"[Followup] Starting follow-up generation with {len(messages)} messages")

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
                elif role in ('assistant', 'ai'):
                    conversation_lines.append(f"Assistant: {content}")

            conversation_text = "\n".join(conversation_lines)

            # Build prompt
            prompt = self.config.prompt_template.format(
                count=self.config.count,
                conversation_text=conversation_text
            )

            # Initialize model
            model_config_service = ModelConfigService()
            model_instance = model_config_service.get_llm_instance(self.config.model_id)

            # Call model with timeout
            logger.info(f"[Followup] Calling model {self.config.model_id}")
            response = await asyncio.wait_for(
                model_instance.ainvoke(prompt),
                timeout=self.config.timeout_seconds
            )

            # Parse response into questions
            raw_text = response.content.strip()
            questions = []

            for line in raw_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Remove common numbering patterns like "1.", "1)", "- ", "* "
                import re
                line = re.sub(r'^[\d]+[.\)]\s*', '', line)
                line = re.sub(r'^[-*]\s*', '', line)
                line = line.strip()
                if line:
                    questions.append(line)

            # Limit to configured count
            questions = questions[:self.config.count]

            logger.info(f"[Followup] Generated {len(questions)} follow-up questions")
            return questions

        except asyncio.TimeoutError:
            logger.error("[Followup] Timeout generating follow-up questions")
            return []
        except Exception as e:
            logger.error(f"[Followup] Failed to generate follow-up questions: {e}")
            return []
