"""Filesystem-based provider plugin loader."""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import re
import sys
import types
from collections.abc import Callable
from pathlib import Path

import yaml

from src.core.paths import repo_root

from .models import ProviderPluginContribution, ProviderPluginManifest, ProviderPluginStatus

logger = logging.getLogger(__name__)


class ProviderPluginLoader:
    """Load provider plugins from manifest directories at startup."""

    def __init__(self, plugins_dir: Path | None = None) -> None:
        self.plugins_dir = plugins_dir or (repo_root() / "plugins")

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
                raw_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                if not isinstance(raw_manifest, dict):
                    raise ValueError("manifest root must be an object")
                if "provider" not in raw_manifest:
                    continue
                manifest = self._load_manifest(raw_manifest, manifest_path=manifest_path)
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
    def _load_manifest(raw: dict[str, object], *, manifest_path: Path) -> ProviderPluginManifest:
        schema_version = int(raw.get("schema_version", 1))
        plugin_id = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        version = str(raw.get("version") or "").strip()
        description = raw.get("description")
        enabled = bool(raw.get("enabled", True))
        provider_section = raw.get("provider")
        if provider_section is None:
            raise ValueError("provider section is required")
        if not isinstance(provider_section, dict):
            raise ValueError("provider section must be an object")
        entrypoint = str(provider_section.get("entrypoint") or "").strip()
        provider_enabled = bool(provider_section.get("enabled", True))

        if schema_version != 1:
            raise ValueError(f"unsupported schema_version: {schema_version}")
        if not plugin_id:
            raise ValueError("id is required")
        if not name:
            raise ValueError("name is required")
        if not version:
            raise ValueError("version is required")
        if not entrypoint:
            raise ValueError("provider.entrypoint is required")

        return ProviderPluginManifest(
            schema_version=schema_version,
            id=plugin_id,
            name=name,
            version=version,
            entrypoint=entrypoint,
            description=(str(description).strip() if description is not None else None),
            enabled=(enabled and provider_enabled),
            directory=manifest_path.parent,
        )

    @staticmethod
    def _load_contribution(manifest: ProviderPluginManifest) -> ProviderPluginContribution:
        register = ProviderPluginLoader._load_entrypoint_callable(
            plugin_id=manifest.id,
            plugin_dir=manifest.directory,
            entrypoint=manifest.entrypoint,
        )
        if register is None or not callable(register):
            raise ValueError("entrypoint callable not found")
        contribution = register()
        if not isinstance(contribution, ProviderPluginContribution):
            raise TypeError(
                "plugin entrypoint must return ProviderPluginContribution, "
                f"got {type(contribution).__name__}"
            )
        return contribution

    @staticmethod
    def _load_entrypoint_callable(
        *,
        plugin_id: str,
        plugin_dir: Path | None,
        entrypoint: str,
    ) -> Callable:
        file_part, separator, callable_name = str(entrypoint or "").partition(":")
        if not separator or not callable_name.strip():
            raise ValueError("entrypoint must use format '<relative_file.py>:<callable>'")
        if plugin_dir is None:
            raise ValueError("plugin directory is required")
        raw_file = file_part.strip()
        if not raw_file:
            raise ValueError("entrypoint file path is required")
        entry_file = ProviderPluginLoader._resolve_entrypoint_file(plugin_dir, raw_file)
        module = ProviderPluginLoader._load_module_from_file(plugin_id, plugin_dir, entry_file)
        register = getattr(module, callable_name.strip(), None)
        if not callable(register):
            raise ValueError("entrypoint callable not found")
        return register

    @staticmethod
    def _resolve_entrypoint_file(plugin_dir: Path, relative_path: str) -> Path:
        resolved_base = plugin_dir.resolve()
        resolved = (resolved_base / relative_path).resolve()
        if resolved_base not in resolved.parents and resolved != resolved_base:
            raise ValueError(f"entrypoint path escapes plugin directory: {relative_path}")
        if not resolved.exists():
            raise FileNotFoundError(f"entrypoint file not found: {resolved}")
        if resolved.suffix.lower() != ".py":
            raise ValueError("entrypoint file must be a .py file")
        return resolved

    @staticmethod
    def _load_module_from_file(plugin_id: str, plugin_dir: Path, entry_file: Path):
        digest = hashlib.sha1(str(plugin_dir.resolve()).encode("utf-8")).hexdigest()[:10]
        package_name = (
            f"_lexmint_plugin_{ProviderPluginLoader._sanitize_identifier(plugin_id)}_{digest}"
        )
        package = sys.modules.get(package_name)
        if package is None:
            package = types.ModuleType(package_name)
            package.__path__ = [str(plugin_dir.resolve())]
            sys.modules[package_name] = package

        relative = entry_file.resolve().relative_to(plugin_dir.resolve()).with_suffix("")
        relative_name = "_".join(relative.parts)
        module_suffix = ProviderPluginLoader._sanitize_identifier(relative_name)
        module_name = f"{package_name}.{module_suffix}"
        existing = sys.modules.get(module_name)
        if existing is not None:
            return existing

        spec = importlib.util.spec_from_file_location(module_name, str(entry_file))
        if spec is None or spec.loader is None:
            raise ValueError(f"failed to create module spec for {entry_file}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _sanitize_identifier(value: str) -> str:
        normalized = re.sub(r"[^0-9a-zA-Z_]", "_", str(value or "").strip())
        if not normalized:
            return "plugin"
        if normalized[0].isdigit():
            return f"p_{normalized}"
        return normalized
