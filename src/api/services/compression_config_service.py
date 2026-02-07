"""
Compression Config Service

Manages configuration for context compression (summarization).
"""
import logging
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

import yaml

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """You are a conversation summarizer. Create a concise but comprehensive summary of the conversation below.

The summary must:
1. Capture all key topics discussed, decisions made, and conclusions reached
2. Preserve specific details needed to continue (names, numbers, code snippets, file paths, URLs, technical terms)
3. Note any unresolved questions or pending tasks
4. Be written for seamless continuation

Conversation to summarize:
{formatted_messages}

Write the summary now. Start with "**Conversation Summary**" and organize by topic if multiple subjects were covered."""


@dataclass
class CompressionConfig:
    """Configuration for context compression"""
    model_id: str
    temperature: float
    min_messages: int
    timeout_seconds: int
    prompt_template: str


class CompressionConfigService:
    """Service for managing compression configuration"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "compression_config.yaml"
        else:
            config_path = Path(config_path)

        self.config_path = config_path
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        """Create default config file if it doesn't exist"""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            default_data = {
                'compression': {
                    'model_id': 'deepseek:deepseek-chat',
                    'temperature': 0.3,
                    'min_messages': 2,
                    'timeout_seconds': 60,
                    'prompt_template': DEFAULT_PROMPT_TEMPLATE,
                }
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_data, f, allow_unicode=True, default_flow_style=False)
            logger.info(f"Created default compression config at {self.config_path}")

    def _load_config(self) -> CompressionConfig:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            config_data = data.get('compression', {})
            return CompressionConfig(
                model_id=config_data.get('model_id', 'deepseek:deepseek-chat'),
                temperature=config_data.get('temperature', 0.3),
                min_messages=config_data.get('min_messages', 2),
                timeout_seconds=config_data.get('timeout_seconds', 60),
                prompt_template=config_data.get('prompt_template', DEFAULT_PROMPT_TEMPLATE),
            )
        except Exception as e:
            logger.error(f"Failed to load compression config: {e}")
            return CompressionConfig(
                model_id='deepseek:deepseek-chat',
                temperature=0.3,
                min_messages=2,
                timeout_seconds=60,
                prompt_template=DEFAULT_PROMPT_TEMPLATE,
            )

    def reload_config(self):
        """Reload configuration from file"""
        self.config = self._load_config()

    def save_config(self, updates: Dict):
        """Save updated configuration to file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            if 'compression' not in data:
                data['compression'] = {}

            for key, value in updates.items():
                if value is not None:
                    data['compression'][key] = value

            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

            self.reload_config()
            logger.info("Compression config updated successfully")
        except Exception as e:
            logger.error(f"Failed to save compression config: {e}")
            raise
