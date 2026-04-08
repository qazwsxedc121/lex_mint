"""Tests for regex-based tool-gate runtime decisions."""

from __future__ import annotations

from types import SimpleNamespace

from src.application.chat.tool_gate_service import ToolGateService


def test_tool_gate_service_applies_highest_priority_match():
    config = SimpleNamespace(
        enabled=True,
        rules=[
            SimpleNamespace(
                id="low_priority",
                enabled=True,
                priority=1,
                pattern="常识",
                flags="",
                include_tools=[],
                exclude_tools=["execute_python"],
            ),
            SimpleNamespace(
                id="high_priority",
                enabled=True,
                priority=10,
                pattern="常识",
                flags="",
                include_tools=["web_search", "read_webpage"],
                exclude_tools=[],
            ),
        ],
    )
    service = ToolGateService()
    decision = service.apply(
        candidate_tool_names={"execute_python", "web_search", "read_webpage"},
        user_message="这是常识问题",
        config=config,
    )

    assert decision.applied is True
    assert decision.matched_rule_id == "high_priority"
    assert decision.final_allowed_tool_names == {"web_search", "read_webpage"}


def test_tool_gate_service_handles_empty_allowed_set():
    config = SimpleNamespace(
        enabled=True,
        rules=[
            SimpleNamespace(
                id="no_tools",
                enabled=True,
                priority=5,
                pattern="不要工具",
                flags="",
                include_tools=[],
                exclude_tools=["execute_python", "web_search"],
            ),
        ],
    )
    service = ToolGateService()
    decision = service.apply(
        candidate_tool_names={"execute_python", "web_search"},
        user_message="不要工具，直接回答",
        config=config,
    )

    assert decision.applied is True
    assert decision.final_allowed_tool_names == set()
