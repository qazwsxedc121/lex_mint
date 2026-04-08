"""Filesystem-based tool plugin loader."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import yaml

from src.core.paths import repo_root

from .models import (
    ChatCapabilityDefinition,
    ToolPluginContribution,
    ToolPluginManifest,
    ToolPluginStatus,
)

logger = logging.getLogger(__name__)


class ToolPluginLoader:
    """Load tool plugins from manifest directories at startup."""

    def __init__(self, plugins_dir: Path | None = None) -> None:
        self.plugins_dir = plugins_dir or (repo_root() / "tool_plugins")

    def load(
        self,
    ) -> tuple[list[tuple[ToolPluginManifest, ToolPluginContribution]], list[ToolPluginStatus]]:
        loaded: list[tuple[ToolPluginManifest, ToolPluginContribution]] = []
        statuses: list[ToolPluginStatus] = []
        seen_ids: set[str] = set()

        if not self.plugins_dir.exists():
            return loaded, statuses

        for plugin_dir in sorted(self.plugins_dir.iterdir(), key=lambda p: p.name):
            if not plugin_dir.is_dir():
                continue
            manifest_path = plugin_dir / "manifest.yaml"
            plugin_id = plugin_dir.name

            if not manifest_path.exists():
                statuses.append(
                    ToolPluginStatus(
                        id=plugin_id,
                        name=plugin_id,
                        version="unknown",
                        entrypoint="",
                        plugin_dir=str(plugin_dir),
                        enabled=False,
                        loaded=False,
                        error="manifest.yaml not found",
                    )
                )
                continue

            try:
                manifest = self._load_manifest(manifest_path)
            except Exception as exc:
                statuses.append(
                    ToolPluginStatus(
                        id=plugin_id,
                        name=plugin_id,
                        version="unknown",
                        entrypoint="",
                        plugin_dir=str(plugin_dir),
                        enabled=False,
                        loaded=False,
                        error=f"invalid manifest: {exc}",
                    )
                )
                continue

            plugin_id = manifest.id
            if plugin_id in seen_ids:
                statuses.append(
                    ToolPluginStatus(
                        id=manifest.id,
                        name=manifest.name,
                        version=manifest.version,
                        entrypoint=manifest.entrypoint,
                        plugin_dir=str(plugin_dir),
                        enabled=manifest.enabled,
                        loaded=False,
                        has_settings_schema=bool(manifest.settings_schema_path),
                        settings_schema_path=manifest.settings_schema_path,
                        settings_defaults_path=manifest.settings_defaults_path,
                        error=f"duplicate plugin id: {manifest.id}",
                    )
                )
                continue
            seen_ids.add(plugin_id)

            if not manifest.enabled:
                statuses.append(
                    ToolPluginStatus(
                        id=manifest.id,
                        name=manifest.name,
                        version=manifest.version,
                        entrypoint=manifest.entrypoint,
                        plugin_dir=str(plugin_dir),
                        enabled=False,
                        loaded=False,
                        has_settings_schema=bool(manifest.settings_schema_path),
                        settings_schema_path=manifest.settings_schema_path,
                        settings_defaults_path=manifest.settings_defaults_path,
                        error=None,
                    )
                )
                continue

            try:
                contribution = self._load_contribution(manifest)
                loaded.append((manifest, contribution))
                statuses.append(
                    ToolPluginStatus(
                        id=manifest.id,
                        name=manifest.name,
                        version=manifest.version,
                        entrypoint=manifest.entrypoint,
                        plugin_dir=str(plugin_dir),
                        enabled=True,
                        loaded=True,
                        definitions_count=len(contribution.definitions),
                        tools_count=len(contribution.tools),
                        has_settings_schema=bool(manifest.settings_schema_path),
                        settings_schema_path=manifest.settings_schema_path,
                        settings_defaults_path=manifest.settings_defaults_path,
                        error=None,
                    )
                )
            except Exception as exc:
                logger.warning("Failed to load tool plugin %s: %s", manifest.id, exc, exc_info=True)
                statuses.append(
                    ToolPluginStatus(
                        id=manifest.id,
                        name=manifest.name,
                        version=manifest.version,
                        entrypoint=manifest.entrypoint,
                        plugin_dir=str(plugin_dir),
                        enabled=True,
                        loaded=False,
                        has_settings_schema=bool(manifest.settings_schema_path),
                        settings_schema_path=manifest.settings_schema_path,
                        settings_defaults_path=manifest.settings_defaults_path,
                        error=str(exc),
                    )
                )

        return loaded, statuses

    @staticmethod
    def _load_manifest(manifest_path: Path) -> ToolPluginManifest:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("manifest root must be an object")

        schema_version = int(raw.get("schema_version", 1))
        plugin_id = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        version = str(raw.get("version") or "").strip()
        entrypoint = str(raw.get("entrypoint") or "").strip()
        description = raw.get("description")
        enabled = bool(raw.get("enabled", True))
        settings_schema_path_raw = raw.get("settings_schema_path")
        settings_defaults_path_raw = raw.get("settings_defaults_path")
        settings_schema_path = (
            str(settings_schema_path_raw).strip() if settings_schema_path_raw is not None else None
        )
        settings_defaults_path = (
            str(settings_defaults_path_raw).strip()
            if settings_defaults_path_raw is not None
            else None
        )
        if settings_schema_path == "":
            settings_schema_path = None
        if settings_defaults_path == "":
            settings_defaults_path = None
        chat_capabilities = ToolPluginLoader._load_chat_capabilities(
            raw.get("chat_capabilities"),
            plugin_id=plugin_id,
        )

        if schema_version != 1:
            raise ValueError(f"unsupported schema_version: {schema_version}")
        if not plugin_id:
            raise ValueError("id is required")
        if not name:
            raise ValueError("name is required")
        if not version:
            raise ValueError("version is required")
        if not entrypoint:
            raise ValueError("entrypoint is required")

        return ToolPluginManifest(
            schema_version=schema_version,
            id=plugin_id,
            name=name,
            version=version,
            entrypoint=entrypoint,
            description=(str(description).strip() if description is not None else None),
            enabled=enabled,
            settings_schema_path=settings_schema_path,
            settings_defaults_path=settings_defaults_path,
            chat_capabilities=chat_capabilities,
            directory=manifest_path.parent,
        )

    @staticmethod
    def _load_chat_capabilities(
        raw: object,
        *,
        plugin_id: str,
    ) -> list[ChatCapabilityDefinition]:
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValueError("chat_capabilities must be a list when provided")

        seen_ids: set[str] = set()
        capabilities: list[ChatCapabilityDefinition] = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("chat_capabilities entries must be objects")
            capability_id = str(item.get("id") or "").strip()
            if not capability_id:
                raise ValueError("chat_capabilities[].id is required")
            if capability_id in seen_ids:
                raise ValueError(f"duplicate chat_capabilities id: {capability_id}")
            seen_ids.add(capability_id)
            title_i18n_key = str(item.get("title_i18n_key") or "").strip()
            description_i18n_key = str(item.get("description_i18n_key") or "").strip()
            if not title_i18n_key:
                raise ValueError(f"chat_capabilities[{capability_id}].title_i18n_key is required")
            if not description_i18n_key:
                raise ValueError(
                    f"chat_capabilities[{capability_id}].description_i18n_key is required"
                )
            icon_raw = item.get("icon")
            icon = str(icon_raw).strip() if icon_raw is not None else None
            if icon == "":
                icon = None
            order_raw = item.get("order", 1000)
            try:
                order = int(order_raw)
            except Exception:
                raise ValueError(
                    f"chat_capabilities[{capability_id}].order must be an integer"
                ) from None

            capabilities.append(
                ChatCapabilityDefinition(
                    id=capability_id,
                    title_i18n_key=title_i18n_key,
                    description_i18n_key=description_i18n_key,
                    icon=icon,
                    order=order,
                    default_enabled=bool(item.get("default_enabled", False)),
                    visible_in_input=bool(item.get("visible_in_input", True)),
                    plugin_id=plugin_id,
                )
            )
        return capabilities

    @staticmethod
    def _load_contribution(manifest: ToolPluginManifest) -> ToolPluginContribution:
        module_name, separator, callable_name = manifest.entrypoint.partition(":")
        if not separator or not callable_name.strip():
            raise ValueError("entrypoint must use format 'module.path:function_name'")

        module = importlib.import_module(module_name.strip())
        factory = getattr(module, callable_name.strip(), None)
        if not callable(factory):
            raise ValueError(f"entrypoint function not callable: {manifest.entrypoint}")

        contribution = factory()
        if not isinstance(contribution, ToolPluginContribution):
            raise ValueError(
                f"plugin entrypoint must return ToolPluginContribution, got {type(contribution).__name__}"
            )
        return contribution
