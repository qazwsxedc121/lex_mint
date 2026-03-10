"""Compatibility re-export for file reference config service."""

from src.infrastructure.config.file_reference_config_service import (
    FileReferenceConfig,
    FileReferenceConfigService,
)

__all__ = ["FileReferenceConfig", "FileReferenceConfigService"]
