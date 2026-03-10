"""Regression tests for config services that should follow defaults YAML."""

import asyncio
from pathlib import Path
from unittest.mock import Mock

import yaml

from src.infrastructure.config.assistant_config_service import AssistantConfigService
from src.api.services.compression_config_service import CompressionConfigService
from src.api.services.followup_service import FollowupService
from src.api.services.title_generation_service import TitleGenerationService
from src.api.services.translation_config_service import TranslationConfigService


def _load_defaults(filename: str, section: str) -> dict:
    with open(Path("config/defaults") / filename, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get(section, {})


def test_title_generation_service_falls_back_to_defaults_yaml(tmp_path):
    config_path = tmp_path / "title_generation_config.yaml"
    config_path.write_text("title_generation: [", encoding="utf-8")

    service = TitleGenerationService(storage=Mock(), config_path=str(config_path))
    defaults = _load_defaults("title_generation_config.yaml", "title_generation")

    assert service.config.model_id == defaults["model_id"]
    assert service.config.timeout_seconds == defaults["timeout_seconds"]


def test_translation_config_service_falls_back_to_defaults_yaml(tmp_path):
    config_path = tmp_path / "translation_config.yaml"
    config_path.write_text("translation: [", encoding="utf-8")

    service = TranslationConfigService(config_path=str(config_path))
    defaults = _load_defaults("translation_config.yaml", "translation")

    assert service.config.model_id == defaults["model_id"]
    assert service.config.target_language == defaults["target_language"]


def test_compression_config_service_falls_back_to_defaults_yaml(tmp_path):
    config_path = tmp_path / "compression_config.yaml"
    config_path.write_text("compression: [", encoding="utf-8")

    service = CompressionConfigService(config_path=str(config_path))
    defaults = _load_defaults("compression_config.yaml", "compression")

    assert service.config.model_id == defaults["model_id"]
    assert service.config.compression_strategy == defaults["compression_strategy"]


def test_followup_service_falls_back_to_defaults_yaml(tmp_path):
    config_path = tmp_path / "followup_config.yaml"
    config_path.write_text("followup: [", encoding="utf-8")

    service = FollowupService(config_path=str(config_path))
    defaults = _load_defaults("followup_config.yaml", "followup")

    assert service.config.model_id == defaults["model_id"]
    assert service.config.count == defaults["count"]


def test_assistant_config_service_uses_empty_defaults_yaml(tmp_path):
    config_path = tmp_path / "assistants_config.yaml"

    service = AssistantConfigService(config_path=config_path)
    config = asyncio.run(service.load_config())

    assert config.default == ""
    assert config.assistants == []

