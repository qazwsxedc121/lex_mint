"""Plugin loader and runtime registry for session export formats."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import re
import sys
import types
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from src.core.paths import repo_root

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportArtifact:
    """Renderable export payload."""

    format: str
    media_type: str
    filename: str
    content_bytes: bytes


@dataclass(frozen=True)
class SessionExportFormatDefinition:
    """One export format declaration."""

    id: str
    display_name: str
    media_type: str
    extension: str


@dataclass(frozen=True)
class SessionExportFormatInfo:
    """One available runtime export format."""

    id: str
    display_name: str
    media_type: str
    extension: str
    source: str
    plugin_id: str | None = None
    plugin_name: str | None = None
    plugin_version: str | None = None


@dataclass(frozen=True)
class SessionExportPluginContribution:
    """Runtime contribution from one session export plugin."""

    formats: list[SessionExportFormatDefinition]
    handlers: dict[str, Callable[..., object]]


@dataclass(frozen=True)
class SessionExportPlugin:
    """Loaded session export plugin metadata and contribution."""

    plugin_id: str
    name: str
    version: str
    contribution: SessionExportPluginContribution


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


@dataclass
class _ExportRuntimeEntry:
    definition: SessionExportFormatDefinition
    primary_handler: Callable[..., object]
    primary_source: str
    primary_plugin_id: str | None = None
    primary_plugin_name: str | None = None
    primary_plugin_version: str | None = None
    fallback_handler: Callable[..., object] | None = None
    fallback_source: str | None = None


class SessionExportUnsupportedFormatError(ValueError):
    """Raised when export format is not supported."""

    def __init__(self, export_format: str, available_formats: list[str]) -> None:
        super().__init__(f"Unsupported export format: {export_format}")
        self.export_format = export_format
        self.available_formats = available_formats


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

                contribution = self._load_contribution(plugin_dir=plugin_dir, entrypoint=entrypoint)
                loaded.append(
                    SessionExportPlugin(
                        plugin_id=plugin_id,
                        name=name,
                        version=version,
                        contribution=contribution,
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

    def _load_contribution(
        self, *, plugin_dir: Path, entrypoint: str
    ) -> SessionExportPluginContribution:
        register_callable = self._load_entrypoint_callable(
            plugin_dir=plugin_dir, entrypoint=entrypoint
        )
        raw_contribution = register_callable()
        return self._normalize_contribution(raw_contribution)

    @staticmethod
    def _load_entrypoint_callable(*, plugin_dir: Path, entrypoint: str) -> Callable[..., object]:
        if ":" not in entrypoint:
            raise ValueError("entrypoint must be '<file.py>:<callable>'")
        relative_file, callable_name = entrypoint.split(":", 1)
        module_path = (plugin_dir / relative_file).resolve()
        plugin_root = plugin_dir.resolve()
        if not str(module_path).startswith(str(plugin_root)):
            raise ValueError("entrypoint escapes plugin directory")
        if not module_path.exists():
            raise FileNotFoundError(f"entrypoint file not found: {relative_file}")

        module_hash = hashlib.md5(
            str(module_path).encode("utf-8"), usedforsecurity=False
        ).hexdigest()[:8]
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
        return cast(Callable[..., object], entry_callable)

    @staticmethod
    def _normalize_contribution(raw: object) -> SessionExportPluginContribution:
        if callable(raw):
            logger.warning(
                "Deprecated session export plugin interface detected; "
                "treating callable contribution as markdown formatter."
            )
            markdown_definition = SessionExportFormatDefinition(
                id="markdown",
                display_name="Markdown",
                media_type="text/markdown; charset=utf-8",
                extension="md",
            )
            return SessionExportPluginContribution(
                formats=[markdown_definition],
                handlers={"markdown": raw},
            )

        if isinstance(raw, SessionExportPluginContribution):
            return raw

        if not isinstance(raw, dict):
            raise TypeError("session export contribution must be callable, dataclass, or dict")

        raw_formats = raw.get("formats")
        raw_handlers = raw.get("handlers")
        if not isinstance(raw_formats, list) or not isinstance(raw_handlers, dict):
            raise TypeError(
                "session export contribution dict must include formats(list) and handlers(dict)"
            )

        formats: list[SessionExportFormatDefinition] = []
        seen_format_ids: set[str] = set()
        for item in raw_formats:
            if isinstance(item, SessionExportFormatDefinition):
                definition = item
            elif isinstance(item, dict):
                definition = SessionExportFormatDefinition(
                    id=str(item.get("id") or "").strip(),
                    display_name=str(item.get("display_name") or item.get("id") or "").strip(),
                    media_type=str(item.get("media_type") or "").strip(),
                    extension=str(item.get("extension") or "").strip().lstrip("."),
                )
            else:
                raise TypeError("session export format entry must be object")

            if not definition.id:
                raise ValueError("session export format id is required")
            if definition.id in seen_format_ids:
                raise ValueError(f"duplicate format id in contribution: {definition.id}")
            if not definition.media_type:
                raise ValueError(f"session export format media_type is required: {definition.id}")
            if not definition.extension:
                raise ValueError(f"session export format extension is required: {definition.id}")

            seen_format_ids.add(definition.id)
            formats.append(definition)

        handlers: dict[str, Callable[..., object]] = {}
        for key, value in raw_handlers.items():
            format_id = str(key or "").strip()
            if not format_id:
                continue
            if not callable(value):
                raise TypeError(f"session export handler must be callable: {format_id}")
            handlers[format_id] = value

        for definition in formats:
            if definition.id not in handlers:
                raise ValueError(f"missing handler for format: {definition.id}")

        return SessionExportPluginContribution(formats=formats, handlers=handlers)


def _build_core_markdown(session: dict[str, Any]) -> str:
    title = str(session.get("title") or "Untitled")
    messages = session.get("state", {}).get("messages", [])
    lines = [f"# {title}\n"]

    think_pattern = re.compile(r"<think>(.*?)</think>", re.DOTALL)
    for msg in messages:
        role = msg.get("role", "")
        content = str(msg.get("content", ""))
        if role == "user":
            lines.append("---")
            lines.append("## User\n")
            lines.append(content)
            lines.append("")
            continue
        if role == "assistant":
            lines.append("---")
            lines.append("## Assistant\n")
            match = think_pattern.search(content)
            if match:
                thinking_text = match.group(1).strip()
                main_content = think_pattern.sub("", content).strip()
                content = (
                    f"<details>\n<summary>Thinking</summary>\n\n{thinking_text}\n\n</details>\n\n"
                    f"{main_content}"
                )
            lines.append(content)
            lines.append("")
    return "\n".join(lines)


def _build_core_json_messages(session: dict[str, Any]) -> str:
    messages = session.get("state", {}).get("messages", [])
    normalized: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        normalized.append(
            {
                "role": msg.get("role"),
                "content": msg.get("content"),
                "name": msg.get("name"),
                "tool_calls": msg.get("tool_calls"),
            }
        )
    return json.dumps(normalized, ensure_ascii=False, indent=2)


def _core_runtime_entries() -> dict[str, _ExportRuntimeEntry]:
    markdown_definition = SessionExportFormatDefinition(
        id="markdown",
        display_name="Markdown",
        media_type="text/markdown; charset=utf-8",
        extension="md",
    )
    json_definition = SessionExportFormatDefinition(
        id="json",
        display_name="JSON",
        media_type="application/json; charset=utf-8",
        extension="json",
    )
    return {
        "markdown": _ExportRuntimeEntry(
            definition=markdown_definition,
            primary_handler=_build_core_markdown,
            primary_source="core",
        ),
        "json": _ExportRuntimeEntry(
            definition=json_definition,
            primary_handler=_build_core_json_messages,
            primary_source="core",
        ),
    }


def _build_runtime_registry() -> dict[str, _ExportRuntimeEntry]:
    registry = _core_runtime_entries()
    plugins, _ = SessionExportPluginLoader().load_with_statuses()

    for plugin in plugins:
        for definition in plugin.contribution.formats:
            handler = plugin.contribution.handlers.get(definition.id)
            if handler is None:
                continue
            existing = registry.get(definition.id)
            if existing is None:
                registry[definition.id] = _ExportRuntimeEntry(
                    definition=definition,
                    primary_handler=handler,
                    primary_source="plugin",
                    primary_plugin_id=plugin.plugin_id,
                    primary_plugin_name=plugin.name,
                    primary_plugin_version=plugin.version,
                )
                continue

            registry[definition.id] = _ExportRuntimeEntry(
                definition=definition,
                primary_handler=handler,
                primary_source="plugin",
                primary_plugin_id=plugin.plugin_id,
                primary_plugin_name=plugin.name,
                primary_plugin_version=plugin.version,
                fallback_handler=existing.primary_handler,
                fallback_source=existing.primary_source,
            )
    return registry


_runtime_registry: dict[str, _ExportRuntimeEntry] | None = None


def _ensure_registry() -> dict[str, _ExportRuntimeEntry]:
    global _runtime_registry
    if _runtime_registry is None:
        _runtime_registry = _build_runtime_registry()
    return _runtime_registry


def _safe_file_title(title: str) -> str:
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", title).strip()
    return safe_title or "conversation"


def _normalize_artifact_result(
    *,
    result: object,
    definition: SessionExportFormatDefinition,
    title: str,
) -> ExportArtifact:
    filename = f"{_safe_file_title(title)}.{definition.extension}"

    if isinstance(result, ExportArtifact):
        return result
    if isinstance(result, bytes):
        return ExportArtifact(
            format=definition.id,
            media_type=definition.media_type,
            filename=filename,
            content_bytes=result,
        )
    if isinstance(result, str):
        return ExportArtifact(
            format=definition.id,
            media_type=definition.media_type,
            filename=filename,
            content_bytes=result.encode("utf-8"),
        )
    if isinstance(result, (dict, list)):
        return ExportArtifact(
            format=definition.id,
            media_type=definition.media_type,
            filename=filename,
            content_bytes=json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    raise TypeError(f"Unsupported export result type: {type(result).__name__}")


def list_session_export_plugin_statuses() -> list[SessionExportPluginStatus]:
    """Return startup-like status info for session export feature plugins."""
    _, statuses = SessionExportPluginLoader().load_with_statuses()
    return statuses


def list_session_export_formats() -> list[SessionExportFormatInfo]:
    """Return all effective export formats after core + plugin merge."""
    registry = _ensure_registry()
    formats: list[SessionExportFormatInfo] = []
    for key in sorted(registry):
        entry = registry[key]
        formats.append(
            SessionExportFormatInfo(
                id=entry.definition.id,
                display_name=entry.definition.display_name,
                media_type=entry.definition.media_type,
                extension=entry.definition.extension,
                source=entry.primary_source,
                plugin_id=entry.primary_plugin_id,
                plugin_name=entry.primary_plugin_name,
                plugin_version=entry.primary_plugin_version,
            )
        )
    return formats


def export_session_artifact(*, session: dict[str, Any], export_format: str) -> ExportArtifact:
    """Export session by requested format with plugin-first fallback to core."""
    registry = _ensure_registry()
    requested = str(export_format or "").strip().lower() or "markdown"
    entry = registry.get(requested)
    if entry is None:
        available = sorted(registry.keys())
        raise SessionExportUnsupportedFormatError(requested, available)

    title = str(session.get("title") or "conversation")
    try:
        result = entry.primary_handler(session=session)
    except TypeError:
        result = entry.primary_handler(session)
    except Exception as exc:
        if entry.fallback_handler is None:
            raise RuntimeError(f"session export failed for format '{requested}'") from exc
        try:
            fallback_result = entry.fallback_handler(session=session)
        except TypeError:
            fallback_result = entry.fallback_handler(session)
        return _normalize_artifact_result(
            result=fallback_result, definition=entry.definition, title=title
        )

    return _normalize_artifact_result(result=result, definition=entry.definition, title=title)


def build_session_export_markdown(*, session: dict[str, Any]) -> str:
    """Compatibility helper for legacy callers expecting markdown text."""
    artifact = export_session_artifact(session=session, export_format="markdown")
    return artifact.content_bytes.decode("utf-8", errors="replace")
