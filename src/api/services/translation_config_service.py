"""Compatibility re-export for translation config service."""

from src.infrastructure.config.translation_config_service import (
    DEFAULT_PROMPT_TEMPLATE,
    TranslationConfig,
    TranslationConfigService,
)

__all__ = ["DEFAULT_PROMPT_TEMPLATE", "TranslationConfig", "TranslationConfigService"]
