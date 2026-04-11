"""Plugin loader and runtime hook for session markdown export."""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import re
import sys
import types
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.core.paths import repo_root

logger = logging.getLogger(__name__)


class SessionExportPluginUnavailable(RuntimeError):
    """Raised when session export plugin is not available."""


@dataclass(frozen=True)
class SessionExportPlugin:
    """Loaded session export plugin metadata and callable."""

    plugin_id: str
    name: str
    version: str
    formatter: Callable[..., str]


@dataclass(frozen=True)
class SessionExportPluginStatus:
    """Session export feature plugin status for management API."""

    id: str
    name: str
    version: str
    entrypoint: str
    plugin_dir: str
    enabled: bool
    loaded: bool
    error: str | None = None


class SessionExportPluginLoader:
    """Load session export feature plugins from plugins directory."""

    def __init__(self, plugins_dir: Path | None = None) -> None:
        self.plugins_dir = plugins_dir or (repo_root() / "plugins")

    def load(self) -> list[SessionExportPlugin]:
        loaded, _ = self.load_with_statuses()
        return loaded

    def load_with_statuses(
        self,
    ) -> tuple[list[SessionExportPlugin], list[SessionExportPluginStatus]]:
        loaded: list[SessionExportPlugin] = []
        statuses: list[SessionExportPluginStatus] = []
        seen_ids: set[str] = set()
        if not self.plugins_dir.exists():
            return loaded, statuses

        for plugin_dir in sorted(self.plugins_dir.iterdir(), key=lambda p: p.name):
            if not plugin_dir.is_dir():
                continue
            manifest_path = plugin_dir / "manifest.yaml"
            if not manifest_path.exists():
                continue

            plugin_id = plugin_dir.name
            try:
                raw_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                if not isinstance(raw_manifest, dict):
                    continue

                plugin_id = str(raw_manifest.get("id") or "").strip() or plugin_id
                name = str(raw_manifest.get("name") or "").strip() or plugin_id
                version = str(raw_manifest.get("version") or "").strip() or "unknown"

                feature_section = raw_manifest.get("feature")
                if not isinstance(feature_section, dict):
                    continue
                export_section = feature_section.get("session_export")
                if not isinstance(export_section, dict):
                    continue

                enabled = bool(raw_manifest.get("enabled", True)) and bool(
                    export_section.get("enabled", True)
                )
                entrypoint = str(export_section.get("entrypoint") or "").strip()
                if plugin_id in seen_ids:
                    statuses.append(
                        SessionExportPluginStatus(
                            id=plugin_id,
                            name=name,
                            version=version,
                            entrypoint=entrypoint,
                            plugin_dir=str(plugin_dir),
                            enabled=enabled,
                            loaded=False,
                            error=f"duplicate plugin id: {plugin_id}",
                        )
                    )
                    continue
                seen_ids.add(plugin_id)

                if not enabled:
                    statuses.append(
                        SessionExportPluginStatus(
                            id=plugin_id,
                            name=name,
                            version=version,
                            entrypoint=entrypoint,
                            plugin_dir=str(plugin_dir),
                            enabled=False,
                            loaded=False,
                        )
                    )
                    continue

                if not entrypoint:
                    statuses.append(
                        SessionExportPluginStatus(
                            id=plugin_id,
                            name=name,
                            version=version,
                            entrypoint="",
                            plugin_dir=str(plugin_dir),
                            enabled=True,
                            loaded=False,
                            error="feature.session_export.entrypoint is required",
                        )
                    )
                    continue

                formatter = self._load_formatter(plugin_dir=plugin_dir, entrypoint=entrypoint)
                loaded.append(
                    SessionExportPlugin(
                        plugin_id=plugin_id,
                        name=name,
                        version=version,
                        formatter=formatter,
                    )
                )
                statuses.append(
                    SessionExportPluginStatus(
                        id=plugin_id,
                        name=name,
                        version=version,
                        entrypoint=entrypoint,
                        plugin_dir=str(plugin_dir),
                        enabled=True,
                        loaded=True,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Failed to load session export plugin from %s: %s",
                    plugin_dir,
                    exc,
                    exc_info=True,
                )
                statuses.append(
                    SessionExportPluginStatus(
                        id=plugin_id,
                        name=plugin_id,
                        version="unknown",
                        entrypoint="",
                        plugin_dir=str(plugin_dir),
                        enabled=True,
                        loaded=False,
                        error=str(exc),
                    )
                )
        return loaded, statuses

    @staticmethod
    def _load_formatter(*, plugin_dir: Path, entrypoint: str) -> Callable[..., str]:
        if ":" not in entrypoint:
            raise ValueError("entrypoint must be '<file.py>:<callable>'")
        relative_file, callable_name = entrypoint.split(":", 1)
        module_path = (plugin_dir / relative_file).resolve()
        plugin_root = plugin_dir.resolve()
        if not str(module_path).startswith(str(plugin_root)):
            raise ValueError("entrypoint escapes plugin directory")
        if not module_path.exists():
            raise FileNotFoundError(f"entrypoint file not found: {relative_file}")

        module_hash = hashlib.md5(str(module_path).encode("utf-8"), usedforsecurity=False).hexdigest()[
            :8
        ]
        module_name = re.sub(r"\W+", "_", f"session_export_{plugin_dir.name}_{module_hash}")
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to import module from {module_path}")

        module = importlib.util.module_from_spec(spec)
        assert isinstance(module, types.ModuleType)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        entry_callable = getattr(module, callable_name, None)
        if entry_callable is None or not callable(entry_callable):
            raise TypeError(f"callable not found: {entrypoint}")

        formatter = entry_callable()
        if formatter is None or not callable(formatter):
            raise TypeError("entrypoint must return a callable formatter")
        return formatter


_loaded_plugin: SessionExportPlugin | None = None
_plugins_initialized = False


def _load_first_plugin() -> SessionExportPlugin | None:
    loaded, _ = SessionExportPluginLoader().load_with_statuses()
    if not loaded:
        return None
    if len(loaded) > 1:
        logger.warning(
            "Multiple session export plugins loaded (%s); using first: %s",
            len(loaded),
            loaded[0].plugin_id,
        )
    return loaded[0]


def list_session_export_plugin_statuses() -> list[SessionExportPluginStatus]:
    """Return startup-like status info for session export feature plugins."""
    _, statuses = SessionExportPluginLoader().load_with_statuses()
    return statuses


def build_session_export_markdown(
    *,
    session: dict[str, Any],
) -> str:
    """Render markdown via plugin formatter."""
    global _plugins_initialized, _loaded_plugin
    if not _plugins_initialized:
        _loaded_plugin = _load_first_plugin()
        _plugins_initialized = True

    plugin = _loaded_plugin
    if plugin is None:
        raise SessionExportPluginUnavailable("session export plugin is not enabled")

    try:
        return plugin.formatter(session=session)
    except TypeError:
        return plugin.formatter(session)
    except Exception as exc:
        raise RuntimeError(f"session export plugin failed: {plugin.plugin_id}") from exc
