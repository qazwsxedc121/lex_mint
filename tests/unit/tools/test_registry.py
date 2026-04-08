"""Unit tests for builtin tool registry and shared tool metadata."""

from __future__ import annotations

import json

from src.tools.registry import ToolRegistry


def test_builtin_registry_exposes_all_builtin_tools():
    registry = ToolRegistry()

    tool_names = [tool.name for tool in registry.get_all_tools()]

    assert tool_names == [
        "get_current_time",
        "execute_python",
        "execute_javascript",
        "simple_calculator",
        "format_json",
        "text_statistics",
        "web_search",
        "read_webpage",
    ]


def test_builtin_registry_execute_format_json():
    registry = ToolRegistry()

    result = registry.execute_tool(
        "format_json",
        {"value": '{"b":1,"a":2}', "indent": 2, "sort_keys": True},
    )

    assert result == '{\n  "a": 2,\n  "b": 1\n}'


def test_builtin_registry_execute_text_statistics():
    registry = ToolRegistry()

    result = registry.execute_tool("text_statistics", {"text": "hello world\nsecond line"})
    payload = json.loads(result)

    assert payload == {
        "chars": 23,
        "chars_no_whitespace": 20,
        "words": 4,
        "lines": 2,
        "utf8_bytes": 23,
    }


def test_builtin_registry_default_project_map_tracks_definitions():
    registry = ToolRegistry()

    assert registry.get_default_project_enabled_map() == {
        "get_current_time": False,
        "execute_python": True,
        "execute_javascript": True,
        "simple_calculator": False,
        "format_json": False,
        "text_statistics": False,
        "web_search": False,
        "read_webpage": False,
        "read_project_document": True,
        "read_current_document": True,
        "search_project_text": True,
        "apply_diff_project_document": False,
        "apply_diff_current_document": False,
        "search_knowledge": True,
        "read_knowledge": True,
    }
