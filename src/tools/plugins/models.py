"""Data models for tool plugin manifests and loaded contributions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool

from src.tools.definitions import ToolDefinition


@dataclass(frozen=True)
class ChatCapabilityOptionDefinition:
    """One selectable option for a chat input capability control."""

    value: str
    label_i18n_key: str
    description_i18n_key: str | None = None


@dataclass(frozen=True)
class ChatCapabilityDefinition:
    """One chat input capability exposed by a plugin."""

    id: str
    title_i18n_key: str
    description_i18n_key: str
    control_type: str = "toggle"  # "toggle" | "select"
    arg_key: str = "value"
    options: list[ChatCapabilityOptionDefinition] = field(default_factory=list)
    default_value: str | None = None
    tool_group: str | None = None
    prefer_tool_execution: bool = False
    context_keys: list[str] = field(default_factory=list)
    source_types: list[str] = field(default_factory=list)
    icon: str | None = None
    order: int = 1000
    default_enabled: bool = False
    visible_in_input: bool = True
    plugin_id: str | None = None
    plugin_name: str | None = None
    plugin_version: str | None = None


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
    settings_schema_path: str | None = None
    settings_defaults_path: str | None = None
    chat_capabilities: list[ChatCapabilityDefinition] = field(default_factory=list)
    directory: Path | None = None


@dataclass(frozen=True)
class ToolPluginContribution:
    """Runtime contributions exported by one plugin entrypoint."""

    definitions: list[ToolDefinition] = field(default_factory=list)
    tools: list[BaseTool] = field(default_factory=list)
    tool_handlers: dict[str, Any] = field(default_factory=dict)
    context_capability_handlers: dict[str, Any] = field(default_factory=dict)


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
    has_settings_schema: bool = False
    settings_schema_path: str | None = None
    settings_defaults_path: str | None = None
    error: str | None = None
