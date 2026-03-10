"""Compatibility re-export for compression configuration service."""

from src.infrastructure.compression.compression_config_service import (
    CompressionConfig,
    CompressionConfigService,
    DEFAULT_PROMPT_TEMPLATE,
)

__all__ = ["CompressionConfig", "CompressionConfigService", "DEFAULT_PROMPT_TEMPLATE"]

