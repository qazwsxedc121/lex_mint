"""Built-in provider definitions loaded from tracked defaults config."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import yaml

from src.core.paths import config_defaults_dir

from .plugins import ProviderPluginLoader
from .types import ProviderDefinition

logger = logging.getLogger(__name__)


def _load_builtin_provider_entries() -> list[dict[str, Any]]:
    defaults_dir = config_defaults_dir()
    provider_path = defaults_dir / "provider_config.yaml"
    if not provider_path.exists():
        logger.warning("Builtin provider defaults file not found: %s", provider_path)
        return []

    try:
        with open(provider_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning("Failed to load builtin providers from %s: %s", provider_path, exc)
        return []

    providers = data.get("providers") if isinstance(data, dict) else None
    return providers if isinstance(providers, list) else []


def _coerce_provider_definition(entry: dict[str, Any]) -> ProviderDefinition | None:
    if not isinstance(entry, dict):
        return None
    if str(entry.get("type") or "builtin") != "builtin":
        return None

    payload = {key: value for key, value in entry.items() if key in ProviderDefinition.model_fields}
    default_profile_id = entry.get("default_endpoint_profile_id") or entry.get(
        "endpoint_profile_id"
    )
    if default_profile_id and "default_endpoint_profile_id" not in payload:
        payload["default_endpoint_profile_id"] = default_profile_id

    try:
        return ProviderDefinition(**payload)
    except Exception as exc:
        logger.warning("Skipping invalid builtin provider definition %s: %s", entry.get("id"), exc)
        return None


def _load_plugin_builtin_provider_entries() -> list[ProviderDefinition]:
    loaded_plugins, statuses = ProviderPluginLoader().load()
    definitions: list[ProviderDefinition] = []

    for status in statuses:
        if status.enabled and not status.loaded:
            logger.warning(
                "Provider plugin %s failed to load while collecting builtin providers: %s",
                status.id,
                status.error,
            )

    for manifest, contribution in loaded_plugins:
        for definition in contribution.builtin_providers:
            if not isinstance(definition, ProviderDefinition):
                logger.warning(
                    "Ignoring invalid builtin provider definition from plugin %s",
                    manifest.id,
                )
                continue
            definitions.append(definition)

    return definitions


@lru_cache(maxsize=1)
def _plugin_builtin_provider_source_map() -> dict[str, dict[str, str]]:
    loaded_plugins, statuses = ProviderPluginLoader().load()
    source_map: dict[str, dict[str, str]] = {}

    for status in statuses:
        if status.enabled and not status.loaded:
            logger.warning(
                "Provider plugin %s failed to load while collecting builtin provider sources: %s",
                status.id,
                status.error,
            )

    for manifest, contribution in loaded_plugins:
        for definition in contribution.builtin_providers:
            if not isinstance(definition, ProviderDefinition):
                continue
            source_map[definition.id] = {
                "plugin_id": manifest.id,
                "plugin_name": manifest.name,
                "plugin_version": manifest.version,
            }
    return source_map


@lru_cache(maxsize=1)
def _builtin_provider_map() -> dict[str, ProviderDefinition]:
    providers: dict[str, ProviderDefinition] = {}
    for entry in _load_builtin_provider_entries():
        definition = _coerce_provider_definition(entry)
        if definition is None:
            continue
        providers[definition.id] = definition

    for definition in _load_plugin_builtin_provider_entries():
        if definition.id in providers:
            logger.info(
                "Builtin provider '%s' overridden by provider plugin definition",
                definition.id,
            )
        providers[definition.id] = definition

    return providers


BUILTIN_PROVIDERS: dict[str, ProviderDefinition] = _builtin_provider_map()


def get_builtin_provider(provider_id: str) -> ProviderDefinition | None:
    return _builtin_provider_map().get(provider_id)


def get_all_builtin_providers() -> dict[str, ProviderDefinition]:
    return _builtin_provider_map().copy()


def is_builtin_provider(provider_id: str) -> bool:
    return provider_id in _builtin_provider_map()


def get_builtin_provider_plugin_source(provider_id: str) -> dict[str, str] | None:
    """Return plugin source metadata for one builtin provider when available."""
    source = _plugin_builtin_provider_source_map().get(provider_id)
    if source is None:
        return None
    return source.copy()
