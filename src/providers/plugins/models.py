"""Data models for provider plugin manifests and loaded contributions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.providers.base import BaseLLMAdapter
from src.providers.types import ProviderDefinition


@dataclass(frozen=True)
class ProviderPluginManifest:
    """One parsed provider plugin manifest file."""

    schema_version: int
    id: str
    name: str
    version: str
    entrypoint: str
    description: str | None = None
    enabled: bool = True
    directory: Path | None = None


@dataclass(frozen=True)
class ProviderPluginContribution:
    """Runtime contributions exported by one provider plugin entrypoint."""

    adapters: dict[str, type[BaseLLMAdapter]] = field(default_factory=dict)
    builtin_providers: list[ProviderDefinition] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderPluginStatus:
    """Status object for provider plugin diagnostics."""

    id: str
    name: str
    version: str
    entrypoint: str
    plugin_dir: str
    enabled: bool
    loaded: bool
    adapters_count: int = 0
    builtin_providers_count: int = 0
    error: str | None = None
