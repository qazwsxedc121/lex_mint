"""Unit tests for AssistantToolPolicyResolver."""

import pytest

from src.infrastructure.config.assistant_tool_policy_resolver import AssistantToolPolicyResolver


@pytest.mark.asyncio
async def test_assistant_tool_policy_filters_candidates_with_assistant_map():
    resolver = AssistantToolPolicyResolver()
    assistant_obj = type(
        "AssistantLike",
        (),
        {"tool_enabled_map": {"simple_calculator": True, "format_json": False}},
    )()

    allowed = await resolver.get_allowed_tool_names(
        assistant_id="writer",
        assistant_obj=assistant_obj,
        candidate_tool_names=["simple_calculator", "format_json", "get_current_time"],
    )

    assert "simple_calculator" in allowed
    assert "format_json" not in allowed
    # Builtin defaults are respected for unspecified tools.
    assert "get_current_time" not in allowed


@pytest.mark.asyncio
async def test_assistant_tool_policy_ignores_manual_disable_for_knowledge_tools():
    resolver = AssistantToolPolicyResolver()
    assistant_obj = type(
        "AssistantLike",
        (),
        {"tool_enabled_map": {"search_knowledge": False, "read_knowledge": False}},
    )()

    allowed = await resolver.get_allowed_tool_names(
        assistant_id="writer",
        assistant_obj=assistant_obj,
        candidate_tool_names=["search_knowledge", "read_knowledge"],
    )

    # Knowledge tools follow KB availability and are not manually configurable.
    assert "search_knowledge" in allowed
    assert "read_knowledge" in allowed
