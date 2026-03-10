"""Compression-related infrastructure modules."""

from .compression_config_service import CompressionConfig, CompressionConfigService, DEFAULT_PROMPT_TEMPLATE
from .compression_service import CompressionService

__all__ = [
    "CompressionConfig",
    "CompressionConfigService",
    "DEFAULT_PROMPT_TEMPLATE",
    "CompressionService",
]

