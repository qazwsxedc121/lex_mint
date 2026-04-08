"""Tests for tool description override config service."""

from __future__ import annotations

from src.infrastructure.config.tool_description_config_service import ToolDescriptionConfigService


def test_tool_description_config_service_loads_and_saves_overrides(tmp_path):
    config_path = tmp_path / "tool_description_config.yaml"
    service = ToolDescriptionConfigService(config_path=str(config_path))

    assert config_path.exists()
    assert isinstance(service.default_descriptions, dict)
    assert service.config.overrides == {}

    service.save_overrides({"execute_python": "custom python guidance"})
    assert service.config.overrides.get("execute_python") == "custom python guidance"
    effective = service.get_effective_description_map()
    assert effective.get("execute_python") == "custom python guidance"


def test_tool_description_config_service_ignores_unknown_and_blank_overrides(tmp_path):
    config_path = tmp_path / "tool_description_config.yaml"
    service = ToolDescriptionConfigService(config_path=str(config_path))
    service.save_overrides(
        {
            "unknown_tool": "should be ignored",
            "execute_python": "   ",
        }
    )
    assert service.config.overrides == {}
