"""
Translation Config Service

Manages configuration for Q&A translation.
"""
import logging
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

import yaml

from .yaml_config_utils import load_default_yaml_section, load_layered_yaml_section, save_yaml_section_updates
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
        self.defaults_path: Optional[Path] = config_defaults_dir() / "translation_config.yaml"
        self.legacy_paths: list[Path] = []

        if config_path is None:
            self.config_path = config_local_dir() / "translation_config.yaml"
            self.legacy_paths = [legacy_config_dir() / "translation_config.yaml"]
        else:
            self.config_path = Path(config_path)
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        """Create default config file if it doesn't exist"""
        ensure_local_file(
            local_path=self.config_path,
            defaults_path=self.defaults_path,
            legacy_paths=self.legacy_paths,
            initial_text=yaml.safe_dump({"translation": {}}, allow_unicode=True, sort_keys=False),
        )

    def _load_default_section(self) -> Dict:
        """Load fallback defaults from the repo default config file."""
        return load_default_yaml_section(self.defaults_path, 'translation')

    def _load_config(self) -> TranslationConfig:
        """Load configuration from YAML file"""
        default_config, config_data = load_layered_yaml_section(
            config_path=self.config_path,
            defaults_path=self.defaults_path,
            legacy_paths=self.legacy_paths,
            section_name='translation',
            logger=logger,
            error_label='translation config',
        )

        return TranslationConfig(
            enabled=config_data.get('enabled', default_config.get('enabled', True)),
            target_language=config_data.get('target_language', default_config.get('target_language', 'Chinese')),
            input_target_language=config_data.get(
                'input_target_language',
                default_config.get('input_target_language', 'English'),
            ),
            provider=config_data.get('provider', default_config.get('provider', 'model_config')),
            model_id=config_data.get('model_id', default_config.get('model_id', '')),
            local_gguf_model_path=config_data.get(
                'local_gguf_model_path',
                default_config.get('local_gguf_model_path', 'models/llm/local-translate.gguf'),
            ),
            local_gguf_n_ctx=config_data.get('local_gguf_n_ctx', default_config.get('local_gguf_n_ctx', 8192)),
            local_gguf_n_threads=config_data.get(
                'local_gguf_n_threads',
                default_config.get('local_gguf_n_threads', 0),
            ),
            local_gguf_n_gpu_layers=config_data.get(
                'local_gguf_n_gpu_layers',
                default_config.get('local_gguf_n_gpu_layers', 0),
            ),
            local_gguf_max_tokens=config_data.get(
                'local_gguf_max_tokens',
                default_config.get('local_gguf_max_tokens', 2048),
            ),
            temperature=config_data.get('temperature', default_config.get('temperature', 0.3)),
            timeout_seconds=config_data.get('timeout_seconds', default_config.get('timeout_seconds', 30)),
            prompt_template=config_data.get(
                'prompt_template',
                default_config.get('prompt_template', DEFAULT_PROMPT_TEMPLATE),
            ),
        )

    def reload_config(self):
        """Reload configuration from file"""
        self.config = self._load_config()

    def save_config(self, updates: Dict):
        """Save updated configuration to file"""
        try:
            save_yaml_section_updates(
                config_path=self.config_path,
                section_name='translation',
                updates=updates,
            )
            self.reload_config()
            logger.info("Translation config updated successfully")
        except Exception as e:
            logger.error(f"Failed to save translation config: {e}")
            raise
