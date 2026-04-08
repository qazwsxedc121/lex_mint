"""Central registry for builtin tools used by function calling."""

from __future__ import annotations

import logging
from dataclasses import replace

from langchain_core.tools import BaseTool

from .definitions import ToolDefinition
from .plugins import ToolPluginLoader, ToolPluginStatus

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for plugin-backed tools and shared metadata."""

    def __init__(self) -> None:
        loaded_plugins, plugin_statuses = ToolPluginLoader().load()
        self._plugin_statuses = list(plugin_statuses)

        definitions: list[ToolDefinition] = []
        tools: list[BaseTool] = []
        handler_map: dict[str, object] = {}

        for manifest, contribution in loaded_plugins:
            for definition in contribution.definitions:
                definitions.append(
                    replace(
                        definition,
                        plugin_id=manifest.id,
                        plugin_name=manifest.name,
                        plugin_version=manifest.version,
                    )
                )

            tools.extend(contribution.tools)

            for tool_name, handler in contribution.tool_handlers.items():
                name = str(tool_name or "").strip()
                if not name:
                    continue
                if name in handler_map:
                    logger.warning(
                        "Skipping duplicate tool handler for %s from plugin %s",
                        name,
                        manifest.id,
                    )
                    continue
                handler_map[name] = handler

        self._definitions = self._dedupe_definitions(definitions)
        self._definition_map: dict[str, ToolDefinition] = {
            definition.name: definition for definition in self._definitions
        }
        self._tools = self._dedupe_tools(tools)
        self._tool_map = {tool.name: tool for tool in self._tools}
        self._tool_handler_map = handler_map

    @staticmethod
    def _dedupe_definitions(definitions: list[ToolDefinition]) -> list[ToolDefinition]:
        deduped: list[ToolDefinition] = []
        seen_names: set[str] = set()
        for definition in definitions:
            if definition.name in seen_names:
                logger.warning("Skipping duplicate tool definition: %s", definition.name)
                continue
            seen_names.add(definition.name)
            deduped.append(definition)
        return deduped

    @staticmethod
    def _dedupe_tools(tools: list[BaseTool]) -> list[BaseTool]:
        deduped: list[BaseTool] = []
        seen_names: set[str] = set()
        for tool in tools:
            name = str(getattr(tool, "name", "") or "").strip()
            if not name:
                continue
            if name in seen_names:
                logger.warning("Skipping duplicate tool object: %s", name)
                continue
            seen_names.add(name)
            deduped.append(tool)
        return deduped

    def get_all_tools(self) -> list[BaseTool]:
        """Return all registered tool objects for LangChain bind_tools()."""
        return list(self._tools)

    def get_all_definitions(self) -> list[ToolDefinition]:
        """Return tool definition metadata for registry consumers."""
        return list(self._definitions)

    def get_tool_by_name(self, name: str) -> BaseTool | None:
        """Look up a tool by name."""
        return self._tool_map.get(name)

    def get_definition_by_name(self, name: str) -> ToolDefinition | None:
        """Look up tool metadata by name."""
        return self._definition_map.get(name)

    def execute_tool(self, name: str, args: dict) -> str:
        """Execute a builtin tool by name with validated LangChain args."""
        handler = self._tool_handler_map.get(name)
        if handler is None:
            return f"Error: Unknown tool '{name}'"

        try:
            result = handler(**(args or {}))
            return str(result)
        except Exception as exc:
            logger.error("Tool execution error (%s): %s", name, exc, exc_info=True)
            return f"Error executing {name}: {exc}"

    def get_default_project_enabled_map(self) -> dict[str, bool]:
        """Default per-project enablement state for all registered tool definitions."""
        return {definition.name: definition.enabled_by_default for definition in self._definitions}

    def get_plugin_statuses(self) -> list[ToolPluginStatus]:
        """Return startup plugin load statuses for diagnostics and settings UI."""
        return list(self._plugin_statuses)


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get the global ToolRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
