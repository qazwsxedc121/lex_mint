"""Tests for ToolLoopRunner message appending behavior."""

from langchain_core.messages import AIMessage, ToolMessage

from src.llm_runtime.tool_loop_runner import ToolLoopRunner, ToolLoopState


def test_append_round_with_tool_results_preserves_reasoning_content():
    state = ToolLoopState(current_messages=[])

    ToolLoopRunner.append_round_with_tool_results(
        state,
        round_content="Need to call a tool",
        round_tool_calls=[{"name": "simple_calculator", "args": {"expr": "1+1"}, "id": "call_1"}],
        tool_results=[{"name": "simple_calculator", "result": "2", "tool_call_id": "call_1"}],
        round_reasoning="I should calculate first.",
    )

    assert len(state.current_messages) == 2
    assert isinstance(state.current_messages[0], AIMessage)
    assert isinstance(state.current_messages[1], ToolMessage)

    ai_msg = state.current_messages[0]
    assert ai_msg.additional_kwargs.get("reasoning_content") == "I should calculate first."
    assert len(ai_msg.tool_calls) == 1
    assert ai_msg.tool_calls[0]["name"] == "simple_calculator"


def test_append_round_with_tool_results_without_reasoning_stays_compatible():
    state = ToolLoopState(current_messages=[])

    ToolLoopRunner.append_round_with_tool_results(
        state,
        round_content="Need to call a tool",
        round_tool_calls=[{"name": "simple_calculator", "args": {"expr": "1+1"}, "id": "call_1"}],
        tool_results=[{"name": "simple_calculator", "result": "2", "tool_call_id": "call_1"}],
    )

    ai_msg = state.current_messages[0]
    assert isinstance(ai_msg, AIMessage)
    assert ai_msg.additional_kwargs == {}


def test_append_round_with_tool_results_preserves_reasoning_details():
    state = ToolLoopState(current_messages=[])
    details = [{"type": "reasoning.text", "text": "keep-me"}]

    ToolLoopRunner.append_round_with_tool_results(
        state,
        round_content="Need to call a tool",
        round_tool_calls=[{"name": "simple_calculator", "args": {"expr": "1+1"}, "id": "call_1"}],
        tool_results=[{"name": "simple_calculator", "result": "2", "tool_call_id": "call_1"}],
        round_reasoning_details=details,
    )

    ai_msg = state.current_messages[0]
    assert isinstance(ai_msg, AIMessage)
    assert ai_msg.additional_kwargs.get("reasoning_details") == details


def test_resolve_max_tool_rounds_expands_for_web_research():
    max_rounds = ToolLoopRunner.resolve_max_tool_rounds(
        tool_names={"web_search", "read_webpage"},
        latest_user_text="How many studio albums were published by Mercedes Sosa between 2000 and 2009?",
    )

    assert max_rounds == 6


def test_record_round_activity_tracks_stalled_web_research():
    runner = ToolLoopRunner(max_tool_rounds=5)
    state = ToolLoopState(current_messages=[], web_research_enabled=True, max_tool_rounds=5)

    first_round_calls = [
        {"name": "web_search", "args": {"query": "1928 olympics athletes"}, "id": "call_1"}
    ]
    first_round_results = [
        {"name": "web_search", "result": '{"ok": true, "results": []}', "tool_call_id": "call_1"}
    ]
    runner.record_round_activity(
        state, round_tool_calls=first_round_calls, tool_results=first_round_results
    )

    assert state.no_progress_rounds == 0

    duplicate_calls = [
        {"name": "web_search", "args": {"query": "1928 olympics athletes"}, "id": "call_2"}
    ]
    duplicate_results = [
        {"name": "web_search", "result": '{"ok": true, "results": []}', "tool_call_id": "call_2"}
    ]
    runner.record_round_activity(
        state, round_tool_calls=duplicate_calls, tool_results=duplicate_results
    )
    runner.record_round_activity(
        state, round_tool_calls=duplicate_calls, tool_results=duplicate_results
    )

    assert state.no_progress_rounds == 2

    forced = runner.advance_round_or_force_finalize(state, round_content="stalled")

    assert forced is True
    assert state.force_finalize_without_tools is True
    assert state.tool_finalize_reason == "stalled_research_force_finalize"
