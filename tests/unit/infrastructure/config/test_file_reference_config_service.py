"""Tests for file reference config service."""

from __future__ import annotations

from src.infrastructure.config.file_reference_config_service import FileReferenceConfigService


def test_file_reference_config_service_creates_loads_and_saves_config(tmp_path):
    config_path = tmp_path / "file_reference_config.yaml"

    service = FileReferenceConfigService(config_path=config_path)
    assert config_path.exists()
    assert service.config.ui_preview_max_chars == 1200
    assert service.config.max_chunks == 6

    config_path.write_text(
        """
file_reference:
  ui_preview_max_chars: "1500"
  ui_preview_max_lines: -2
  injection_preview_max_chars: "oops"
  injection_preview_max_lines: 20
  chunk_size: 3000
  max_chunks: 8
  total_budget_chars: 20000
""".strip(),
        encoding="utf-8",
    )
    service.reload_config()

    assert service.config.ui_preview_max_chars == 1500
    assert service.config.ui_preview_max_lines == 28
    assert service.config.injection_preview_max_chars == 600
    assert service.config.injection_preview_max_lines == 20
    assert service.config.chunk_size == 3000
    assert service.config.max_chunks == 8
    assert service.config.total_budget_chars == 20000

    service.save_config({"max_chunks": 9, "ui_preview_max_lines": 30})
    reloaded = FileReferenceConfigService(config_path=config_path)
    assert reloaded.config.max_chunks == 9
    assert reloaded.config.ui_preview_max_lines == 30


def test_file_reference_config_service_falls_back_to_defaults_on_bad_yaml(tmp_path):
    config_path = tmp_path / "file_reference_config.yaml"
    config_path.write_text("file_reference: [", encoding="utf-8")

    service = FileReferenceConfigService(config_path=config_path)
    assert service.config.ui_preview_max_chars == 1200
    assert service.config.total_budget_chars == 18000
