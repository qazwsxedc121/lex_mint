"""Shared settings helpers for the web_tools plugin."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from src.core.paths import repo_root
from src.infrastructure.config.tool_plugin_settings_service import ToolPluginSettingsService

WEB_TOOLS_PLUGIN_ID = "web_tools"
_DEFAULTS_FILE = "settings.defaults.yaml"


def _deep_merge(base: Any, updates: Any) -> Any:
    if isinstance(base, dict) and isinstance(updates, dict):
        merged: dict[str, Any] = {k: deepcopy(v) for k, v in base.items()}
        for key, value in updates.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    if updates is None:
        return deepcopy(base)
    return deepcopy(updates)


def _plugin_dir() -> Path:
    return repo_root() / "plugins" / WEB_TOOLS_PLUGIN_ID


def load_web_tools_defaults() -> dict[str, Any]:
    plugin_dir = _plugin_dir()
    defaults_path = plugin_dir / _DEFAULTS_FILE
    if not defaults_path.exists():
        return {}
    data = yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def load_effective_web_tools_settings() -> dict[str, Any]:
    service = ToolPluginSettingsService()
    defaults = load_web_tools_defaults()
    user_settings = service.get_plugin_settings(WEB_TOOLS_PLUGIN_ID)
    return service.merge_effective_settings(defaults, user_settings)


def save_web_tools_settings_updates(updates: dict[str, Any]) -> dict[str, Any]:
    service = ToolPluginSettingsService()
    current = service.get_plugin_settings(WEB_TOOLS_PLUGIN_ID)
    next_settings = _deep_merge(current, updates)
    if not isinstance(next_settings, dict):
        next_settings = {}
    service.save_plugin_settings(WEB_TOOLS_PLUGIN_ID, next_settings)
    return next_settings
