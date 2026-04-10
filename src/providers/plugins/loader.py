"""Filesystem-based provider plugin loader."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import yaml

from src.core.paths import repo_root

from .models import ProviderPluginContribution, ProviderPluginManifest, ProviderPluginStatus

logger = logging.getLogger(__name__)


class ProviderPluginLoader:
    """Load provider plugins from manifest directories at startup."""

    def __init__(self, plugins_dir: Path | None = None) -> None:
        self.plugins_dir = plugins_dir or (repo_root() / "provider_plugins")

    def load(
        self,
    ) -> tuple[
        list[tuple[ProviderPluginManifest, ProviderPluginContribution]], list[ProviderPluginStatus]
    ]:
        loaded: list[tuple[ProviderPluginManifest, ProviderPluginContribution]] = []
        statuses: list[ProviderPluginStatus] = []
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
                    ProviderPluginStatus(
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
                    ProviderPluginStatus(
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
                    ProviderPluginStatus(
                        id=manifest.id,
                        name=manifest.name,
                        version=manifest.version,
                        entrypoint=manifest.entrypoint,
                        plugin_dir=str(plugin_dir),
                        enabled=manifest.enabled,
                        loaded=False,
                        error=f"duplicate plugin id: {manifest.id}",
                    )
                )
                continue
            seen_ids.add(plugin_id)

            if not manifest.enabled:
                statuses.append(
                    ProviderPluginStatus(
                        id=manifest.id,
                        name=manifest.name,
                        version=manifest.version,
                        entrypoint=manifest.entrypoint,
                        plugin_dir=str(plugin_dir),
                        enabled=False,
                        loaded=False,
                        error=None,
                    )
                )
                continue

            try:
                contribution = self._load_contribution(manifest)
                loaded.append((manifest, contribution))
                statuses.append(
                    ProviderPluginStatus(
                        id=manifest.id,
                        name=manifest.name,
                        version=manifest.version,
                        entrypoint=manifest.entrypoint,
                        plugin_dir=str(plugin_dir),
                        enabled=True,
                        loaded=True,
                        adapters_count=len(contribution.adapters),
                        builtin_providers_count=len(contribution.builtin_providers),
                        error=None,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Failed to load provider plugin %s: %s",
                    manifest.id,
                    exc,
                    exc_info=True,
                )
                statuses.append(
                    ProviderPluginStatus(
                        id=manifest.id,
                        name=manifest.name,
                        version=manifest.version,
                        entrypoint=manifest.entrypoint,
                        plugin_dir=str(plugin_dir),
                        enabled=True,
                        loaded=False,
                        error=str(exc),
                    )
                )

        return loaded, statuses

    @staticmethod
    def _load_manifest(manifest_path: Path) -> ProviderPluginManifest:
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

        return ProviderPluginManifest(
            schema_version=schema_version,
            id=plugin_id,
            name=name,
            version=version,
            entrypoint=entrypoint,
            description=(str(description).strip() if description is not None else None),
            enabled=enabled,
            directory=manifest_path.parent,
        )

    @staticmethod
    def _load_contribution(manifest: ProviderPluginManifest) -> ProviderPluginContribution:
        module_name, separator, attr_name = manifest.entrypoint.partition(":")
        if not separator:
            raise ValueError("entrypoint must use '<module>:<callable>' format")
        module = importlib.import_module(module_name.strip())
        register = getattr(module, attr_name.strip(), None)
        if register is None or not callable(register):
            raise ValueError("entrypoint callable not found")
        contribution = register()
        if not isinstance(contribution, ProviderPluginContribution):
            raise TypeError(
                "plugin entrypoint must return ProviderPluginContribution, "
                f"got {type(contribution).__name__}"
            )
        return contribution
