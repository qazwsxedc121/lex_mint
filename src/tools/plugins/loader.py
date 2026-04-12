"""Filesystem-based tool plugin loader."""

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

from src.core.paths import repo_root, source_repo_root

from .models import (
    ChatCapabilityDefinition,
    ChatCapabilityOptionDefinition,
    ToolPluginContribution,
    ToolPluginManifest,
    ToolPluginStatus,
)

logger = logging.getLogger(__name__)


class ToolPluginLoader:
    """Load tool plugins from manifest directories at startup."""

    def __init__(self, plugins_dir: Path | None = None) -> None:
        self.plugins_dir = plugins_dir or self._default_plugins_dir()

    @staticmethod
    def _default_plugins_dir() -> Path:
        runtime_plugins_dir = repo_root() / "plugins"
        if runtime_plugins_dir.exists():
            return runtime_plugins_dir

        source_plugins_dir = source_repo_root() / "plugins"
        if source_plugins_dir.exists():
            return source_plugins_dir

        return runtime_plugins_dir

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
                raw_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                if not isinstance(raw_manifest, dict):
                    raise ValueError("manifest root must be an object")
                if "tool" not in raw_manifest:
                    continue
                manifest = self._load_manifest(raw_manifest, manifest_path=manifest_path)
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
    def _load_manifest(raw: dict[str, object], *, manifest_path: Path) -> ToolPluginManifest:
        schema_version = int(raw.get("schema_version", 1))
        plugin_id = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        version = str(raw.get("version") or "").strip()
        description = raw.get("description")
        enabled = bool(raw.get("enabled", True))
        tool_section = raw.get("tool")
        if tool_section is None:
            raise ValueError("tool section is required")
        if not isinstance(tool_section, dict):
            raise ValueError("tool section must be an object")

        entrypoint = str(tool_section.get("entrypoint") or "").strip()
        tool_enabled = bool(tool_section.get("enabled", True))
        settings_schema_path_raw = tool_section.get("settings_schema_path")
        settings_defaults_path_raw = tool_section.get("settings_defaults_path")
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
            tool_section.get("chat_capabilities"),
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
            raise ValueError("tool.entrypoint is required")

        return ToolPluginManifest(
            schema_version=schema_version,
            id=plugin_id,
            name=name,
            version=version,
            entrypoint=entrypoint,
            description=(str(description).strip() if description is not None else None),
            enabled=(enabled and tool_enabled),
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
            control_type = str(item.get("control_type") or "toggle").strip().lower()
            if control_type not in {"toggle", "select"}:
                raise ValueError(
                    f"chat_capabilities[{capability_id}].control_type must be 'toggle' or 'select'"
                )
            arg_key = str(item.get("arg_key") or "value").strip()
            if not arg_key:
                raise ValueError(f"chat_capabilities[{capability_id}].arg_key is required")
            order_raw = item.get("order", 1000)
            try:
                order = int(order_raw)
            except Exception:
                raise ValueError(
                    f"chat_capabilities[{capability_id}].order must be an integer"
                ) from None
            options = ToolPluginLoader._load_chat_capability_options(
                item.get("options"),
                capability_id=capability_id,
                control_type=control_type,
            )
            default_value_raw = item.get("default_value")
            default_value = (
                str(default_value_raw).strip() if default_value_raw is not None else None
            )
            if default_value == "":
                default_value = None
            if control_type == "select":
                if not options:
                    raise ValueError(
                        f"chat_capabilities[{capability_id}].options is required for select control"
                    )
                if default_value is None:
                    default_value = options[0].value
                allowed_values = {opt.value for opt in options}
                if default_value not in allowed_values:
                    raise ValueError(
                        f"chat_capabilities[{capability_id}].default_value must exist in options"
                    )
            tool_group_raw = item.get("tool_group")
            tool_group = str(tool_group_raw).strip() if tool_group_raw is not None else None
            if tool_group == "":
                tool_group = None
            context_keys = ToolPluginLoader._normalize_str_list(
                item.get("context_keys"),
                field_name=f"chat_capabilities[{capability_id}].context_keys",
            )
            source_types = ToolPluginLoader._normalize_str_list(
                item.get("source_types"),
                field_name=f"chat_capabilities[{capability_id}].source_types",
            )

            capabilities.append(
                ChatCapabilityDefinition(
                    id=capability_id,
                    title_i18n_key=title_i18n_key,
                    description_i18n_key=description_i18n_key,
                    control_type=control_type,
                    arg_key=arg_key,
                    options=options,
                    default_value=default_value,
                    tool_group=tool_group,
                    prefer_tool_execution=bool(item.get("prefer_tool_execution", False)),
                    context_keys=context_keys,
                    source_types=source_types,
                    icon=icon,
                    order=order,
                    default_enabled=bool(item.get("default_enabled", False)),
                    visible_in_input=bool(item.get("visible_in_input", True)),
                    plugin_id=plugin_id,
                )
            )
        return capabilities

    @staticmethod
    def _load_chat_capability_options(
        raw: object,
        *,
        capability_id: str,
        control_type: str,
    ) -> list[ChatCapabilityOptionDefinition]:
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValueError(f"chat_capabilities[{capability_id}].options must be a list")

        options: list[ChatCapabilityOptionDefinition] = []
        seen_values: set[str] = set()
        for idx, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(
                    f"chat_capabilities[{capability_id}].options[{idx}] must be an object"
                )
            value = str(item.get("value") or "").strip()
            if not value:
                raise ValueError(
                    f"chat_capabilities[{capability_id}].options[{idx}].value is required"
                )
            if value in seen_values:
                raise ValueError(
                    f"duplicate option value for chat_capabilities[{capability_id}]: {value}"
                )
            seen_values.add(value)
            label_i18n_key = str(item.get("label_i18n_key") or "").strip()
            if not label_i18n_key:
                raise ValueError(
                    f"chat_capabilities[{capability_id}].options[{idx}].label_i18n_key is required"
                )
            description_raw = item.get("description_i18n_key")
            description_i18n_key = (
                str(description_raw).strip() if description_raw is not None else None
            )
            if description_i18n_key == "":
                description_i18n_key = None
            options.append(
                ChatCapabilityOptionDefinition(
                    value=value,
                    label_i18n_key=label_i18n_key,
                    description_i18n_key=description_i18n_key,
                )
            )

        if control_type == "toggle" and options:
            raise ValueError(
                f"chat_capabilities[{capability_id}] toggle control cannot define options"
            )
        return options

    @staticmethod
    def _normalize_str_list(raw: object, *, field_name: str) -> list[str]:
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValueError(f"{field_name} must be a list")
        normalized: list[str] = []
        for idx, item in enumerate(raw):
            value = str(item or "").strip()
            if not value:
                raise ValueError(f"{field_name}[{idx}] must be a non-empty string")
            normalized.append(value)
        return normalized

    @staticmethod
    def _load_contribution(manifest: ToolPluginManifest) -> ToolPluginContribution:
        factory = ToolPluginLoader._load_entrypoint_callable(
            plugin_id=manifest.id,
            plugin_dir=manifest.directory,
            entrypoint=manifest.entrypoint,
        )
        if not callable(factory):
            raise ValueError(f"entrypoint function not callable: {manifest.entrypoint}")

        contribution = factory()
        if not isinstance(contribution, ToolPluginContribution):
            raise ValueError(
                f"plugin entrypoint must return ToolPluginContribution, got {type(contribution).__name__}"
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
        entry_file = ToolPluginLoader._resolve_entrypoint_file(plugin_dir, raw_file)
        module = ToolPluginLoader._load_module_from_file(plugin_id, plugin_dir, entry_file)
        factory = getattr(module, callable_name.strip(), None)
        if not callable(factory):
            raise ValueError(f"entrypoint function not callable: {entrypoint}")
        return factory

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
            f"_lexmint_plugin_{ToolPluginLoader._sanitize_identifier(plugin_id)}_{digest}"
        )
        package = sys.modules.get(package_name)
        if package is None:
            package = types.ModuleType(package_name)
            package.__path__ = [str(plugin_dir.resolve())]
            sys.modules[package_name] = package

        relative = entry_file.resolve().relative_to(plugin_dir.resolve()).with_suffix("")
        relative_name = "_".join(relative.parts)
        module_suffix = ToolPluginLoader._sanitize_identifier(relative_name)
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
