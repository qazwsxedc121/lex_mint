"""
Translation Config Service

Manages configuration for Q&A translation.
"""
import logging
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

import yaml

from ..paths import (
    config_defaults_dir,
    config_local_dir,
    legacy_config_dir,
    ensure_local_file,
)

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
    provider: str
    model_id: str
    local_gguf_model_path: str
    local_gguf_n_ctx: int
    local_gguf_n_threads: int
    local_gguf_n_gpu_layers: int
    local_gguf_max_tokens: int
    temperature: float
    timeout_seconds: int
    prompt_template: str


class TranslationConfigService:
    """Service for managing translation configuration"""

    def __init__(self, config_path: Optional[str] = None):
        self.defaults_path: Optional[Path] = None
        self.legacy_paths: list[Path] = []

        if config_path is None:
            self.defaults_path = config_defaults_dir() / "translation_config.yaml"
            self.config_path = config_local_dir() / "translation_config.yaml"
            self.legacy_paths = [legacy_config_dir() / "translation_config.yaml"]
        else:
            self.config_path = Path(config_path)
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        """Create default config file if it doesn't exist"""
        if not self.config_path.exists():
            default_data = {
                'translation': {
                    'enabled': True,
                    'target_language': 'Chinese',
                    'input_target_language': 'English',
                    'provider': 'model_config',
                    'model_id': 'deepseek:deepseek-chat',
                    'local_gguf_model_path': 'models/llm/local-translate.gguf',
                    'local_gguf_n_ctx': 8192,
                    'local_gguf_n_threads': 0,
                    'local_gguf_n_gpu_layers': 0,
                    'local_gguf_max_tokens': 2048,
                    'temperature': 0.3,
                    'timeout_seconds': 30,
                    'prompt_template': DEFAULT_PROMPT_TEMPLATE,
                }
            }
            initial_text = yaml.safe_dump(default_data, allow_unicode=True, sort_keys=False)
            ensure_local_file(
                local_path=self.config_path,
                defaults_path=self.defaults_path,
                legacy_paths=self.legacy_paths,
                initial_text=initial_text,
            )
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
                provider=config_data.get('provider', 'model_config'),
                model_id=config_data.get('model_id', 'deepseek:deepseek-chat'),
                local_gguf_model_path=config_data.get('local_gguf_model_path', 'models/llm/local-translate.gguf'),
                local_gguf_n_ctx=config_data.get('local_gguf_n_ctx', 8192),
                local_gguf_n_threads=config_data.get('local_gguf_n_threads', 0),
                local_gguf_n_gpu_layers=config_data.get('local_gguf_n_gpu_layers', 0),
                local_gguf_max_tokens=config_data.get('local_gguf_max_tokens', 2048),
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
                provider='model_config',
                model_id='deepseek:deepseek-chat',
                local_gguf_model_path='models/llm/local-translate.gguf',
                local_gguf_n_ctx=8192,
                local_gguf_n_threads=0,
                local_gguf_n_gpu_layers=0,
                local_gguf_max_tokens=2048,
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
