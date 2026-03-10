"""Compatibility re-export for memory config service."""

from src.infrastructure.config.memory_config_service import (
    MemoryConfig,
    MemoryConfigService,
    MemoryExtractionConfig,
    MemoryRetrievalConfig,
    MemoryScopeConfig,
)

__all__ = [
    "MemoryConfig",
    "MemoryConfigService",
    "MemoryExtractionConfig",
    "MemoryRetrievalConfig",
    "MemoryScopeConfig",
]
