"""Tests for assistant-level default tool policy."""

from src.domain.models.assistant_config import (
    Assistant,
    get_default_assistant_tool_enabled_map,
)


def test_assistant_default_tool_map_contains_expected_core_tools():
    defaults = get_default_assistant_tool_enabled_map()

    assert defaults["get_current_time"] is False
    assert defaults["execute_python"] is True
    assert defaults["execute_javascript"] is True
    assert defaults["simple_calculator"] is False
    assert defaults["format_json"] is False
    assert defaults["text_statistics"] is False
    assert defaults["web_search"] is False
    assert defaults["read_webpage"] is False
    assert defaults["search_knowledge"] is True
    assert defaults["read_knowledge"] is True


def test_assistant_tool_map_merges_partial_overrides():
    assistant = Assistant(
        id="writer",
        name="Writer",
        model_id="deepseek:deepseek-chat",
        tool_enabled_map={"simple_calculator": True},
    )

    assert assistant.tool_enabled_map["simple_calculator"] is True
    # Unspecified tools keep default values.
    assert assistant.tool_enabled_map["web_search"] is False
