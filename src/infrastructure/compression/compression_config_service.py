"""
Compression Config Service

Manages configuration for context compression (summarization).
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.core.paths import (
    config_defaults_dir,
    config_local_dir,
    ensure_local_file,
)
from src.infrastructure.config.yaml_config_utils import (
    load_layered_yaml_section,
    save_yaml_section_updates,
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
    compression_output_language: str
    compression_strategy: str
    hierarchical_chunk_target_tokens: int
    hierarchical_chunk_overlap_messages: int
    hierarchical_reduce_target_tokens: int
    hierarchical_reduce_overlap_items: int
    hierarchical_max_levels: int
    quality_guard_enabled: bool
    quality_guard_min_coverage: float
    quality_guard_max_facts: int
    compression_metrics_enabled: bool
    auto_compress_enabled: bool
    auto_compress_threshold: float


class CompressionConfigService:
    """Service for managing compression configuration"""

    def __init__(self, config_path: str | None = None):
        self.defaults_path: Path | None = config_defaults_dir() / "compression_config.yaml"

        if config_path is None:
            self.config_path = config_local_dir() / "compression_config.yaml"
        else:
            self.config_path = Path(config_path)
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        """Create default config file if it doesn't exist"""
        ensure_local_file(
            local_path=self.config_path,
            defaults_path=self.defaults_path,
            initial_text=yaml.safe_dump({"compression": {}}, allow_unicode=True, sort_keys=False),
        )

    def _load_config(self) -> CompressionConfig:
        """Load configuration from YAML file"""
        default_config, config_data = load_layered_yaml_section(
            config_path=self.config_path,
            defaults_path=self.defaults_path,
            section_name="compression",
            logger=logger,
            error_label="compression config",
        )

        return CompressionConfig(
            provider=config_data.get("provider", default_config.get("provider", "model_config")),
            model_id=config_data.get("model_id", default_config.get("model_id", "")),
            local_gguf_model_path=config_data.get(
                "local_gguf_model_path",
                default_config.get("local_gguf_model_path", "models/llm/local-summarizer.gguf"),
            ),
            local_gguf_n_ctx=config_data.get(
                "local_gguf_n_ctx", default_config.get("local_gguf_n_ctx", 8192)
            ),
            local_gguf_n_threads=config_data.get(
                "local_gguf_n_threads",
                default_config.get("local_gguf_n_threads", 0),
            ),
            local_gguf_n_gpu_layers=config_data.get(
                "local_gguf_n_gpu_layers",
                default_config.get("local_gguf_n_gpu_layers", 0),
            ),
            local_gguf_max_tokens=config_data.get(
                "local_gguf_max_tokens",
                default_config.get("local_gguf_max_tokens", 2048),
            ),
            temperature=config_data.get("temperature", default_config.get("temperature", 0.3)),
            min_messages=config_data.get("min_messages", default_config.get("min_messages", 2)),
            timeout_seconds=config_data.get(
                "timeout_seconds", default_config.get("timeout_seconds", 60)
            ),
            prompt_template=config_data.get(
                "prompt_template",
                default_config.get("prompt_template", DEFAULT_PROMPT_TEMPLATE),
            ),
            compression_output_language=config_data.get(
                "compression_output_language",
                default_config.get("compression_output_language", "auto"),
            ),
            compression_strategy=config_data.get(
                "compression_strategy",
                default_config.get("compression_strategy", "hierarchical"),
            ),
            hierarchical_chunk_target_tokens=config_data.get(
                "hierarchical_chunk_target_tokens",
                default_config.get("hierarchical_chunk_target_tokens", 0),
            ),
            hierarchical_chunk_overlap_messages=config_data.get(
                "hierarchical_chunk_overlap_messages",
                default_config.get("hierarchical_chunk_overlap_messages", 2),
            ),
            hierarchical_reduce_target_tokens=config_data.get(
                "hierarchical_reduce_target_tokens",
                default_config.get("hierarchical_reduce_target_tokens", 0),
            ),
            hierarchical_reduce_overlap_items=config_data.get(
                "hierarchical_reduce_overlap_items",
                default_config.get("hierarchical_reduce_overlap_items", 1),
            ),
            hierarchical_max_levels=config_data.get(
                "hierarchical_max_levels",
                default_config.get("hierarchical_max_levels", 4),
            ),
            quality_guard_enabled=config_data.get(
                "quality_guard_enabled",
                default_config.get("quality_guard_enabled", True),
            ),
            quality_guard_min_coverage=config_data.get(
                "quality_guard_min_coverage",
                default_config.get("quality_guard_min_coverage", 0.75),
            ),
            quality_guard_max_facts=config_data.get(
                "quality_guard_max_facts",
                default_config.get("quality_guard_max_facts", 24),
            ),
            compression_metrics_enabled=config_data.get(
                "compression_metrics_enabled",
                default_config.get("compression_metrics_enabled", True),
            ),
            auto_compress_enabled=config_data.get(
                "auto_compress_enabled",
                default_config.get("auto_compress_enabled", False),
            ),
            auto_compress_threshold=config_data.get(
                "auto_compress_threshold",
                default_config.get("auto_compress_threshold", 0.5),
            ),
        )

    def reload_config(self):
        """Reload configuration from file"""
        self.config = self._load_config()

    def save_config(self, updates: dict):
        """Save updated configuration to file"""
        try:
            save_yaml_section_updates(
                config_path=self.config_path,
                section_name="compression",
                updates=updates,
            )
            self.reload_config()
            logger.info("Compression config updated successfully")
        except Exception as e:
            logger.error(f"Failed to save compression config: {e}")
            raise
