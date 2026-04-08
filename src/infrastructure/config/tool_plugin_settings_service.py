"""Tool plugin settings config service."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.core.paths import config_local_dir, ensure_local_file
from src.infrastructure.config.yaml_config_utils import (
    load_layered_yaml_section,
    save_yaml_section_updates,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolPluginSettingsConfig:
    """Persisted plugin settings keyed by plugin id."""

    plugins: dict[str, dict[str, Any]]


def _normalize_plugins(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for raw_plugin_id, raw_entry in value.items():
        plugin_id = str(raw_plugin_id or "").strip()
        if not plugin_id:
            continue
        if not isinstance(raw_entry, dict):
            continue
        raw_settings = raw_entry.get("settings", raw_entry)
        if isinstance(raw_settings, dict):
            normalized[plugin_id] = deepcopy(raw_settings)
    return normalized


def _deep_merge(defaults: Any, override: Any) -> Any:
    if isinstance(defaults, dict) and isinstance(override, dict):
        merged: dict[str, Any] = {k: deepcopy(v) for k, v in defaults.items()}
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    if override is None:
        return deepcopy(defaults)
    return deepcopy(override)


class ToolPluginSettingsService:
    """Load/save per-plugin settings and schema/default assets."""

    def __init__(self, config_path: str | None = None) -> None:
        if config_path is None:
            self.config_path = config_local_dir() / "tool_plugin_settings.yaml"
        else:
            self.config_path = Path(config_path)
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        ensure_local_file(
            local_path=self.config_path,
            defaults_path=None,
            initial_text=yaml.safe_dump(
                {"tool_plugin_settings": {"plugins": {}}},
                allow_unicode=True,
                sort_keys=False,
            ),
        )

    def _load_config(self) -> ToolPluginSettingsConfig:
        default_config, config_data = load_layered_yaml_section(
            config_path=self.config_path,
            defaults_path=None,
            section_name="tool_plugin_settings",
            logger=logger,
            error_label="tool plugin settings config",
        )
        merged_data = {**default_config, **config_data}
        return ToolPluginSettingsConfig(
            plugins=_normalize_plugins(merged_data.get("plugins", {})),
        )

    def reload_config(self) -> None:
        self.config = self._load_config()

    def get_plugin_settings(self, plugin_id: str) -> dict[str, Any]:
        return deepcopy(self.config.plugins.get(plugin_id, {}))

    def has_plugin_settings(self, plugin_id: str) -> bool:
        return len(self.config.plugins.get(plugin_id, {})) > 0

    def save_plugin_settings(self, plugin_id: str, settings: dict[str, Any]) -> None:
        normalized_id = str(plugin_id or "").strip()
        if not normalized_id:
            raise ValueError("plugin_id is required")
        if not isinstance(settings, dict):
            raise ValueError("settings must be an object")

        next_plugins = deepcopy(self.config.plugins)
        next_plugins[normalized_id] = deepcopy(settings)
        wrapped_plugins = {key: {"settings": value} for key, value in next_plugins.items()}
        save_yaml_section_updates(
            config_path=self.config_path,
            section_name="tool_plugin_settings",
            updates={"plugins": wrapped_plugins},
        )
        self.config = self._load_config()

    @staticmethod
    def resolve_plugin_file_path(plugin_dir: Path, relative_path: str) -> Path:
        raw = str(relative_path or "").strip()
        if not raw:
            raise ValueError("relative_path is required")
        resolved_base = plugin_dir.resolve()
        resolved = (resolved_base / raw).resolve()
        if resolved_base not in resolved.parents and resolved != resolved_base:
            raise ValueError(f"path escapes plugin directory: {relative_path}")
        return resolved

    @classmethod
    def load_schema(cls, plugin_dir: Path, schema_path: str) -> dict[str, Any]:
        path = cls.resolve_plugin_file_path(plugin_dir, schema_path)
        if not path.exists():
            raise FileNotFoundError(f"settings schema file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("settings schema root must be an object")
        return data

    @classmethod
    def load_defaults(cls, plugin_dir: Path, defaults_path: str | None) -> dict[str, Any]:
        if not defaults_path:
            return {}
        path = cls.resolve_plugin_file_path(plugin_dir, defaults_path)
        if not path.exists():
            raise FileNotFoundError(f"settings defaults file not found: {path}")

        suffix = path.suffix.lower()
        content = path.read_text(encoding="utf-8")
        if suffix == ".json":
            data = json.loads(content)
        else:
            data = yaml.safe_load(content) or {}
        if not isinstance(data, dict):
            raise ValueError("settings defaults root must be an object")
        return data

    @staticmethod
    def merge_effective_settings(
        defaults: dict[str, Any],
        user_settings: dict[str, Any],
    ) -> dict[str, Any]:
        merged = _deep_merge(defaults, user_settings)
        if not isinstance(merged, dict):
            return {}
        return merged
