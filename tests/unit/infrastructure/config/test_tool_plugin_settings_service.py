"""Unit tests for tool plugin settings config service."""

from __future__ import annotations

import json

import pytest

from src.infrastructure.config.tool_plugin_settings_service import ToolPluginSettingsService


def test_service_persists_plugin_settings(tmp_path):
    config_path = tmp_path / "tool_plugin_settings.yaml"
    service = ToolPluginSettingsService(config_path=str(config_path))

    service.save_plugin_settings("demo", {"enabled": True, "timeout_ms": 1500})

    reloaded = ToolPluginSettingsService(config_path=str(config_path))
    assert reloaded.get_plugin_settings("demo") == {"enabled": True, "timeout_ms": 1500}
    assert reloaded.has_plugin_settings("demo") is True


def test_service_loads_schema_and_defaults_and_merges(tmp_path):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    schema_path = plugin_dir / "settings.schema.json"
    defaults_path = plugin_dir / "settings.defaults.yaml"
    schema_path.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "runtime": {
                        "type": "object",
                        "properties": {
                            "dialect": {"type": "string"},
                            "timeout_ms": {"type": "integer", "minimum": 1},
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    defaults_path.write_text(
        "runtime:\n  dialect: sbcl\n  timeout_ms: 1000\n",
        encoding="utf-8",
    )

    schema = ToolPluginSettingsService.load_schema(plugin_dir, "settings.schema.json")
    defaults = ToolPluginSettingsService.load_defaults(plugin_dir, "settings.defaults.yaml")
    merged = ToolPluginSettingsService.merge_effective_settings(
        defaults,
        {"runtime": {"timeout_ms": 2500}},
    )

    assert schema["type"] == "object"
    assert defaults["runtime"]["dialect"] == "sbcl"
    assert merged["runtime"]["dialect"] == "sbcl"
    assert merged["runtime"]["timeout_ms"] == 2500


def test_service_rejects_path_escape(tmp_path):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        ToolPluginSettingsService.resolve_plugin_file_path(plugin_dir, "../outside.json")
