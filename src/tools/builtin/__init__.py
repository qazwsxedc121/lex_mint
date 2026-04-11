"""Builtin tools package with one-file-per-tool plugin structure."""

from __future__ import annotations

from ..definitions import ToolDefinition
from .execute_javascript import TOOL as EXECUTE_JAVASCRIPT_TOOL
from .execute_javascript import build_tool as build_execute_javascript_tool
from .execute_javascript import execute as execute_javascript
from .execute_python import TOOL as EXECUTE_PYTHON_TOOL
from .execute_python import build_tool as build_execute_python_tool
from .execute_python import execute as execute_python

BUILTIN_TOOL_DEFINITIONS: list[ToolDefinition] = [
    EXECUTE_PYTHON_TOOL,
    EXECUTE_JAVASCRIPT_TOOL,
]

_BUILTIN_TOOL_BUILDERS = {
    EXECUTE_PYTHON_TOOL.name: build_execute_python_tool,
    EXECUTE_JAVASCRIPT_TOOL.name: build_execute_javascript_tool,
}

_BUILTIN_TOOL_HANDLERS = {
    EXECUTE_PYTHON_TOOL.name: execute_python,
    EXECUTE_JAVASCRIPT_TOOL.name: execute_javascript,
}


def build_builtin_tools():
    """Build all builtin LangChain tools."""
    return [builder() for builder in _BUILTIN_TOOL_BUILDERS.values()]


def get_builtin_tool_handler(name: str):
    """Look up the builtin handler by tool name."""
    return _BUILTIN_TOOL_HANDLERS.get(name)


def get_builtin_tool_default_enabled_map() -> dict[str, bool]:
    """Project-level default enabled state for builtin tools."""
    return {
        definition.name: definition.enabled_by_default for definition in BUILTIN_TOOL_DEFINITIONS
    }


__all__ = [
    "BUILTIN_TOOL_DEFINITIONS",
    "build_builtin_tools",
    "execute_javascript",
    "execute_python",
    "get_builtin_tool_default_enabled_map",
    "get_builtin_tool_handler",
]
