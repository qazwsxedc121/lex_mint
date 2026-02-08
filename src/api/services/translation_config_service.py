"""
Translation Config Service

Manages configuration for Q&A translation.
"""
import logging
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

import yaml

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """You are a translation expert. Your only task is to translate the following text from its original language to {target_language}. Provide the translation directly without any explanation or commentary. Preserve the original formatting (markdown, code blocks, etc.).

Text to translate:
{text}
"""


@dataclass
class TranslationConfig:
    """Configuration for translation"""
    enabled: bool
    target_language: str
    input_target_language: str
    model_id: str
    temperature: float
    timeout_seconds: int
    prompt_template: str


class TranslationConfigService:
    """Service for managing translation configuration"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "translation_config.yaml"
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
                'translation': {
                    'enabled': True,
                    'target_language': 'Chinese',
                    'input_target_language': 'English',
                    'model_id': 'deepseek:deepseek-chat',
                    'temperature': 0.3,
                    'timeout_seconds': 30,
                    'prompt_template': DEFAULT_PROMPT_TEMPLATE,
                }
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_data, f, allow_unicode=True, default_flow_style=False)
            logger.info(f"Created default translation config at {self.config_path}")

    def _load_config(self) -> TranslationConfig:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            config_data = data.get('translation', {})
            return TranslationConfig(
                enabled=config_data.get('enabled', True),
                target_language=config_data.get('target_language', 'Chinese'),
                input_target_language=config_data.get('input_target_language', 'English'),
                model_id=config_data.get('model_id', 'deepseek:deepseek-chat'),
                temperature=config_data.get('temperature', 0.3),
                timeout_seconds=config_data.get('timeout_seconds', 30),
                prompt_template=config_data.get('prompt_template', DEFAULT_PROMPT_TEMPLATE),
            )
        except Exception as e:
            logger.error(f"Failed to load translation config: {e}")
            return TranslationConfig(
                enabled=True,
                target_language='Chinese',
                input_target_language='English',
                model_id='deepseek:deepseek-chat',
                temperature=0.3,
                timeout_seconds=30,
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

            if 'translation' not in data:
                data['translation'] = {}

            for key, value in updates.items():
                if value is not None:
                    data['translation'][key] = value

            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

            self.reload_config()
            logger.info("Translation config updated successfully")
        except Exception as e:
            logger.error(f"Failed to save translation config: {e}")
            raise
