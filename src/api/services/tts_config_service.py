"""
TTS Config Service

Manages configuration for Text-to-Speech.
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


@dataclass
class TTSConfig:
    """Configuration for TTS"""
    enabled: bool
    voice: str
    voice_zh: str
    rate: str
    volume: str
    max_text_length: int


class TTSConfigService:
    """Service for managing TTS configuration"""

    def __init__(self, config_path: Optional[str] = None):
        self.defaults_path: Optional[Path] = None
        self.legacy_paths: list[Path] = []

        if config_path is None:
            self.defaults_path = config_defaults_dir() / "tts_config.yaml"
            self.config_path = config_local_dir() / "tts_config.yaml"
            self.legacy_paths = [legacy_config_dir() / "tts_config.yaml"]
        else:
            self.config_path = Path(config_path)
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        """Create default config file if it doesn't exist"""
        if not self.config_path.exists():
            default_data = {
                'tts': {
                    'enabled': True,
                    'voice': 'en-US-AriaNeural',
                    'voice_zh': 'zh-CN-XiaoxiaoNeural',
                    'rate': '+0%',
                    'volume': '+0%',
                    'max_text_length': 10000,
                }
            }
            initial_text = yaml.safe_dump(default_data, allow_unicode=True, sort_keys=False)
            ensure_local_file(
                local_path=self.config_path,
                defaults_path=self.defaults_path,
                legacy_paths=self.legacy_paths,
                initial_text=initial_text,
            )
            logger.info(f"Created default TTS config at {self.config_path}")

    def _load_config(self) -> TTSConfig:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            config_data = data.get('tts', {})
            return TTSConfig(
                enabled=config_data.get('enabled', True),
                voice=config_data.get('voice', 'en-US-AriaNeural'),
                voice_zh=config_data.get('voice_zh', 'zh-CN-XiaoxiaoNeural'),
                rate=config_data.get('rate', '+0%'),
                volume=config_data.get('volume', '+0%'),
                max_text_length=config_data.get('max_text_length', 10000),
            )
        except Exception as e:
            logger.error(f"Failed to load TTS config: {e}")
            return TTSConfig(
                enabled=True,
                voice='en-US-AriaNeural',
                voice_zh='zh-CN-XiaoxiaoNeural',
                rate='+0%',
                volume='+0%',
                max_text_length=10000,
            )

    def reload_config(self):
        """Reload configuration from file"""
        self.config = self._load_config()

    def save_config(self, updates: Dict):
        """Save updated configuration to file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            if 'tts' not in data:
                data['tts'] = {}

            for key, value in updates.items():
                if value is not None:
                    data['tts'][key] = value

            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

            self.reload_config()
            logger.info("TTS config updated successfully")
        except Exception as e:
            logger.error(f"Failed to save TTS config: {e}")
            raise
