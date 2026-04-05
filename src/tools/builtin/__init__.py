"""Builtin tools package with one-file-per-tool plugin structure."""

from __future__ import annotations

from ..definitions import ToolDefinition
from .execute_python import TOOL as EXECUTE_PYTHON_TOOL
from .execute_python import build_tool as build_execute_python_tool
from .execute_python import execute as execute_python
from .format_json import TOOL as FORMAT_JSON_TOOL
from .format_json import build_tool as build_format_json_tool
from .format_json import execute as format_json
from .get_current_time import TOOL as GET_CURRENT_TIME_TOOL
from .get_current_time import build_tool as build_get_current_time_tool
from .get_current_time import execute as get_current_time
from .simple_calculator import TOOL as SIMPLE_CALCULATOR_TOOL
from .simple_calculator import build_tool as build_simple_calculator_tool
from .simple_calculator import execute as simple_calculator
from .text_statistics import TOOL as TEXT_STATISTICS_TOOL
from .text_statistics import build_tool as build_text_statistics_tool
from .text_statistics import execute as text_statistics

BUILTIN_TOOL_DEFINITIONS: list[ToolDefinition] = [
    GET_CURRENT_TIME_TOOL,
    EXECUTE_PYTHON_TOOL,
    SIMPLE_CALCULATOR_TOOL,
    FORMAT_JSON_TOOL,
    TEXT_STATISTICS_TOOL,
]

_BUILTIN_TOOL_BUILDERS = {
    GET_CURRENT_TIME_TOOL.name: build_get_current_time_tool,
    EXECUTE_PYTHON_TOOL.name: build_execute_python_tool,
    SIMPLE_CALCULATOR_TOOL.name: build_simple_calculator_tool,
    FORMAT_JSON_TOOL.name: build_format_json_tool,
    TEXT_STATISTICS_TOOL.name: build_text_statistics_tool,
}

_BUILTIN_TOOL_HANDLERS = {
    GET_CURRENT_TIME_TOOL.name: get_current_time,
    EXECUTE_PYTHON_TOOL.name: execute_python,
    SIMPLE_CALCULATOR_TOOL.name: simple_calculator,
    FORMAT_JSON_TOOL.name: format_json,
    TEXT_STATISTICS_TOOL.name: text_statistics,
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
    "execute_python",
    "format_json",
    "get_builtin_tool_default_enabled_map",
    "get_builtin_tool_handler",
    "get_current_time",
    "simple_calculator",
    "text_statistics",
]
