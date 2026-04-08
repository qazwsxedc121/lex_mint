"""Regex-based tool-gate config service for chat tool exposure."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.core.paths import config_defaults_dir, config_local_dir, ensure_local_file
from src.infrastructure.config.yaml_config_utils import (
    load_layered_yaml_section,
    save_yaml_section_updates,
)

logger = logging.getLogger(__name__)

_SUPPORTED_REGEX_FLAGS = {"i", "m", "s"}


@dataclass(frozen=True)
class ToolGateRuleConfig:
    """One regex rule used to gate tool availability."""

    id: str
    enabled: bool = True
    priority: int = 0
    pattern: str = ""
    flags: str = ""
    include_tools: list[str] = field(default_factory=list)
    exclude_tools: list[str] = field(default_factory=list)
    description: str | None = None


@dataclass(frozen=True)
class ToolGateConfig:
    """Configuration for regex-based tool gating."""

    enabled: bool = False
    rules: list[ToolGateRuleConfig] = field(default_factory=list)


def _normalize_tool_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for item in value:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        names.append(name)
        seen.add(name)
    return names


def _normalize_flags(value: Any) -> str:
    raw = str(value or "").strip().lower()
    normalized = []
    seen: set[str] = set()
    for char in raw:
        if char in _SUPPORTED_REGEX_FLAGS and char not in seen:
            normalized.append(char)
            seen.add(char)
    return "".join(normalized)


def _normalize_rules(value: Any) -> list[ToolGateRuleConfig]:
    if not isinstance(value, list):
        return []

    normalized: list[ToolGateRuleConfig] = []
    used_ids: set[str] = set()
    for idx, raw in enumerate(value):
        if not isinstance(raw, dict):
            continue
        rule_id = str(raw.get("id") or "").strip() or f"rule_{idx + 1}"
        if rule_id in used_ids:
            rule_id = f"{rule_id}_{idx + 1}"
        used_ids.add(rule_id)

        pattern = str(raw.get("pattern") or "").strip()
        if not pattern:
            continue
        try:
            priority = int(raw.get("priority", 0))
        except Exception:
            priority = 0

        normalized.append(
            ToolGateRuleConfig(
                id=rule_id,
                enabled=bool(raw.get("enabled", True)),
                priority=priority,
                pattern=pattern,
                flags=_normalize_flags(raw.get("flags", "")),
                include_tools=_normalize_tool_names(raw.get("include_tools", [])),
                exclude_tools=_normalize_tool_names(raw.get("exclude_tools", [])),
                description=(
                    str(raw.get("description")).strip()
                    if raw.get("description") is not None
                    else None
                ),
            )
        )
    return normalized


class ToolGateConfigService:
    """Load/save regex tool-gate configuration."""

    def __init__(self, config_path: str | None = None) -> None:
        self.defaults_path: Path | None = config_defaults_dir() / "tool_gate_config.yaml"
        if config_path is None:
            self.config_path = config_local_dir() / "tool_gate_config.yaml"
        else:
            self.config_path = Path(config_path)
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        ensure_local_file(
            local_path=self.config_path,
            defaults_path=self.defaults_path,
            initial_text=yaml.safe_dump({"tool_gate": {}}, allow_unicode=True, sort_keys=False),
        )

    def _load_config(self) -> ToolGateConfig:
        default_config, config_data = load_layered_yaml_section(
            config_path=self.config_path,
            defaults_path=self.defaults_path,
            section_name="tool_gate",
            logger=logger,
            error_label="tool gate config",
        )
        merged_data = {**default_config, **config_data}
        return ToolGateConfig(
            enabled=bool(merged_data.get("enabled", False)),
            rules=_normalize_rules(merged_data.get("rules")),
        )

    def reload_config(self) -> None:
        self.config = self._load_config()

    def save_config(self, updates: dict[str, object]) -> None:
        save_yaml_section_updates(
            config_path=self.config_path,
            section_name="tool_gate",
            updates=updates,
        )
        self.config = self._load_config()
