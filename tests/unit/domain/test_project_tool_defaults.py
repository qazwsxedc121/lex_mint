"""Tests for project tool default maps derived from shared definitions."""

from __future__ import annotations

from src.domain.models.project_config import get_default_project_tool_enabled_map
from src.tools.builtin import BUILTIN_TOOL_DEFINITIONS
from src.tools.request_scoped import REQUEST_SCOPED_TOOL_DEFINITIONS


def test_project_tool_defaults_match_shared_definitions():
    defaults = get_default_project_tool_enabled_map()

    expected = {
        definition.name: definition.enabled_by_default
        for definition in [*BUILTIN_TOOL_DEFINITIONS, *REQUEST_SCOPED_TOOL_DEFINITIONS]
    }

    assert defaults == expected


def test_project_tool_defaults_include_all_known_tools():
    defaults = get_default_project_tool_enabled_map()

    assert list(defaults.keys()) == [
        "get_current_time",
        "execute_python",
        "simple_calculator",
        "format_json",
        "text_statistics",
        "web_search",
        "read_webpage",
        "read_project_document",
        "read_current_document",
        "search_project_text",
        "apply_diff_project_document",
        "apply_diff_current_document",
        "search_knowledge",
        "read_knowledge",
    ]
