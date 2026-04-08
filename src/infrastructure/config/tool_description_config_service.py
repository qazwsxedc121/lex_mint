"""Tool description override config service."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.core.paths import config_defaults_dir, config_local_dir, ensure_local_file
from src.infrastructure.config.yaml_config_utils import (
    load_layered_yaml_section,
    save_yaml_section_updates,
)
from src.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolDescriptionConfig:
    """Persisted overrides keyed by tool name."""

    overrides: dict[str, str]


def _build_default_description_map() -> dict[str, str]:
    defaults: dict[str, str] = {}
    for definition in get_tool_registry().get_all_definitions():
        defaults[definition.name] = definition.description
    return defaults


def _normalize_overrides(value: Any, known_names: set[str]) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for raw_name, raw_description in value.items():
        name = str(raw_name or "").strip()
        if not name or name not in known_names:
            continue
        description = str(raw_description or "").strip()
        if not description:
            continue
        normalized[name] = description
    return normalized


class ToolDescriptionConfigService:
    """Load/save tool description overrides."""

    def __init__(self, config_path: str | None = None) -> None:
        self.defaults_path: Path | None = config_defaults_dir() / "tool_description_config.yaml"
        if config_path is None:
            self.config_path = config_local_dir() / "tool_description_config.yaml"
        else:
            self.config_path = Path(config_path)
        self.default_descriptions = _build_default_description_map()
        self._known_names = set(self.default_descriptions.keys())
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        ensure_local_file(
            local_path=self.config_path,
            defaults_path=self.defaults_path,
            initial_text=yaml.safe_dump(
                {"tool_descriptions": {"overrides": {}}},
                allow_unicode=True,
                sort_keys=False,
            ),
        )

    def _load_config(self) -> ToolDescriptionConfig:
        default_config, config_data = load_layered_yaml_section(
            config_path=self.config_path,
            defaults_path=self.defaults_path,
            section_name="tool_descriptions",
            logger=logger,
            error_label="tool description config",
        )
        merged_data = {**default_config, **config_data}
        return ToolDescriptionConfig(
            overrides=_normalize_overrides(
                merged_data.get("overrides", {}),
                known_names=self._known_names,
            )
        )

    def reload_config(self) -> None:
        self.config = self._load_config()

    def get_effective_description_map(self) -> dict[str, str]:
        effective = dict(self.default_descriptions)
        effective.update(self.config.overrides)
        return effective

    def save_overrides(self, overrides: dict[str, str | None]) -> None:
        cleaned: dict[str, str] = {}
        for raw_name, raw_description in dict(overrides or {}).items():
            name = str(raw_name or "").strip()
            if not name or name not in self._known_names:
                continue
            description = str(raw_description or "").strip()
            if description:
                cleaned[name] = description
        save_yaml_section_updates(
            config_path=self.config_path,
            section_name="tool_descriptions",
            updates={"overrides": cleaned},
        )
        self.config = self._load_config()
