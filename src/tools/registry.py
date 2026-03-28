"""Central registry for builtin tools used by function calling."""

from __future__ import annotations

import logging

from langchain_core.tools import BaseTool

from .builtin import BUILTIN_TOOL_DEFINITIONS, build_builtin_tools
from .definitions import ToolDefinition

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for globally available builtin tools."""

    def __init__(self) -> None:
        self._definitions: list[ToolDefinition] = list(BUILTIN_TOOL_DEFINITIONS)
        self._definition_map: dict[str, ToolDefinition] = {
            definition.name: definition for definition in self._definitions
        }
        self._tools: list[BaseTool] = build_builtin_tools()
        self._tool_map = {tool.name: tool for tool in self._tools}

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
        tool_obj = self._tool_map.get(name)
        if tool_obj is None:
            return f"Error: Unknown tool '{name}'"

        try:
            result = tool_obj.invoke(args or {})
            return str(result)
        except Exception as exc:
            logger.error("Tool execution error (%s): %s", name, exc, exc_info=True)
            return f"Error executing {name}: {exc}"

    def get_default_project_enabled_map(self) -> dict[str, bool]:
        """Default per-project enablement state for builtin tools."""
        return {definition.name: definition.enabled_by_default for definition in self._definitions}


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get the global ToolRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
