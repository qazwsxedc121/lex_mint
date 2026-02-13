"""
Compression Config Service

Manages configuration for context compression (summarization).
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

DEFAULT_PROMPT_TEMPLATE = """You are a conversation context compressor. Your task is to create a structured summary that preserves essential information while significantly reducing token count.

## Output Format

Structure your summary using these sections (omit empty sections):

### Context
Brief background and conversation setup (1-2 sentences max)

### Key Information
- Critical facts, data, specifications mentioned
- Technical details, configurations, parameters
- Names, identifiers, file paths, URLs

### Decisions & Conclusions
- Decisions made during the conversation
- Agreed-upon solutions or approaches
- Final conclusions reached

### Action Items
- Tasks assigned or planned
- Next steps discussed
- Pending items requiring follow-up

### Code & Technical
```
Preserve essential code snippets, commands, or technical syntax
```

## Rules

### MUST
- Output in the SAME LANGUAGE as the conversation
- Preserve ALL technical terms, code identifiers, file paths, and proper nouns exactly
- Maintain factual accuracy -- never invent or assume information
- Keep code snippets that are essential for context

### SHOULD
- Achieve 60-80% compression ratio (summary should be 20-40% of original length)
- Use bullet points for clarity and scannability
- Preserve chronological order for sequential events
- Consolidate repeated information into single entries

### MAY
- Omit greetings, pleasantries, and filler content
- Combine related points into concise statements
- Abbreviate obvious context when meaning is preserved

## Important
- The summary will be injected into a new conversation as context
- Recipient should be able to continue the conversation seamlessly
- Prioritize information that affects future responses

## Conversation to compress:
{formatted_messages}

Output ONLY the structured summary following the format above. No additional commentary."""


@dataclass
class CompressionConfig:
    """Configuration for context compression"""
    provider: str
    model_id: str
    local_gguf_model_path: str
    local_gguf_n_ctx: int
    local_gguf_n_threads: int
    local_gguf_n_gpu_layers: int
    local_gguf_max_tokens: int
    temperature: float
    min_messages: int
    timeout_seconds: int
    prompt_template: str
    auto_compress_enabled: bool
    auto_compress_threshold: float


class CompressionConfigService:
    """Service for managing compression configuration"""

    def __init__(self, config_path: Optional[str] = None):
        self.defaults_path: Optional[Path] = None
        self.legacy_paths: list[Path] = []

        if config_path is None:
            self.defaults_path = config_defaults_dir() / "compression_config.yaml"
            self.config_path = config_local_dir() / "compression_config.yaml"
            self.legacy_paths = [legacy_config_dir() / "compression_config.yaml"]
        else:
            self.config_path = Path(config_path)
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        """Create default config file if it doesn't exist"""
        if not self.config_path.exists():
            default_data = {
                'compression': {
                    'provider': 'model_config',
                    'model_id': 'deepseek:deepseek-chat',
                    'local_gguf_model_path': 'models/llm/local-summarizer.gguf',
                    'local_gguf_n_ctx': 8192,
                    'local_gguf_n_threads': 0,
                    'local_gguf_n_gpu_layers': 0,
                    'local_gguf_max_tokens': 2048,
                    'temperature': 0.3,
                    'min_messages': 2,
                    'timeout_seconds': 60,
                    'auto_compress_enabled': False,
                    'auto_compress_threshold': 0.5,
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
            logger.info(f"Created default compression config at {self.config_path}")

    def _load_config(self) -> CompressionConfig:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            config_data = data.get('compression', {})
            return CompressionConfig(
                provider=config_data.get('provider', 'model_config'),
                model_id=config_data.get('model_id', 'deepseek:deepseek-chat'),
                local_gguf_model_path=config_data.get('local_gguf_model_path', 'models/llm/local-summarizer.gguf'),
                local_gguf_n_ctx=config_data.get('local_gguf_n_ctx', 8192),
                local_gguf_n_threads=config_data.get('local_gguf_n_threads', 0),
                local_gguf_n_gpu_layers=config_data.get('local_gguf_n_gpu_layers', 0),
                local_gguf_max_tokens=config_data.get('local_gguf_max_tokens', 2048),
                temperature=config_data.get('temperature', 0.3),
                min_messages=config_data.get('min_messages', 2),
                timeout_seconds=config_data.get('timeout_seconds', 60),
                prompt_template=config_data.get('prompt_template', DEFAULT_PROMPT_TEMPLATE),
                auto_compress_enabled=config_data.get('auto_compress_enabled', False),
                auto_compress_threshold=config_data.get('auto_compress_threshold', 0.5),
            )
        except Exception as e:
            logger.error(f"Failed to load compression config: {e}")
            return CompressionConfig(
                provider='model_config',
                model_id='deepseek:deepseek-chat',
                local_gguf_model_path='models/llm/local-summarizer.gguf',
                local_gguf_n_ctx=8192,
                local_gguf_n_threads=0,
                local_gguf_n_gpu_layers=0,
                local_gguf_max_tokens=2048,
                temperature=0.3,
                min_messages=2,
                timeout_seconds=60,
                prompt_template=DEFAULT_PROMPT_TEMPLATE,
                auto_compress_enabled=False,
                auto_compress_threshold=0.5,
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
