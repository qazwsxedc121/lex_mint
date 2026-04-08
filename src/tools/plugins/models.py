"""Data models for tool plugin manifests and loaded contributions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool

from src.tools.definitions import ToolDefinition


@dataclass(frozen=True)
class ToolPluginManifest:
    """One parsed plugin manifest file."""

    schema_version: int
    id: str
    name: str
    version: str
    entrypoint: str
    description: str | None = None
    enabled: bool = True
    directory: Path | None = None


@dataclass(frozen=True)
class ToolPluginContribution:
    """Runtime contributions exported by one plugin entrypoint."""

    definitions: list[ToolDefinition] = field(default_factory=list)
    tools: list[BaseTool] = field(default_factory=list)
    tool_handlers: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolPluginLoadIssue:
    """One plugin load error captured during startup scan."""

    plugin_id: str
    plugin_dir: str
    error: str


@dataclass(frozen=True)
class ToolPluginStatus:
    """Status object exposed to API for plugin diagnostics."""

    id: str
    name: str
    version: str
    entrypoint: str
    plugin_dir: str
    enabled: bool
    loaded: bool
    definitions_count: int = 0
    tools_count: int = 0
    error: str | None = None
