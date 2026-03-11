"""Shared helpers for layered YAML config sections."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from src.core.paths import resolve_layered_read_path


def load_default_yaml_section(defaults_path: Optional[Path], section_name: str) -> dict[str, Any]:
    """Load a defaults YAML section from the tracked repo config."""
    if defaults_path is None or not defaults_path.exists():
        return {}

    with open(defaults_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    section = data.get(section_name, {})
    return section if isinstance(section, dict) else {}


def load_layered_yaml_section(
    *,
    config_path: Path,
    defaults_path: Optional[Path],
    legacy_paths: Optional[list[Path]],
    section_name: str,
    logger: Any,
    error_label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load a layered YAML section with defaults fallback."""
    default_config = load_default_yaml_section(defaults_path, section_name)
    resolved_path = resolve_layered_read_path(
        local_path=config_path,
        defaults_path=defaults_path,
        legacy_paths=legacy_paths,
    )

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        section_data = data.get(section_name, {})
        if not isinstance(section_data, dict):
            section_data = {}
    except Exception as exc:
        logger.error("Failed to load %s: %s", error_label, exc)
        section_data = default_config

    return default_config, section_data


def save_yaml_section_updates(
    *,
    config_path: Path,
    section_name: str,
    updates: dict[str, Any],
) -> None:
    """Persist non-None field updates into a named YAML section."""
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        data = {}

    section = data.get(section_name, {})
    if not isinstance(section, dict):
        section = {}
    data[section_name] = section

    for key, value in updates.items():
        if value is not None:
            section[key] = value

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
