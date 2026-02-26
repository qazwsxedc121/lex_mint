"""Tests for ToolLoopRunner message appending behavior."""

from langchain_core.messages import AIMessage, ToolMessage

from src.agents.tool_loop_runner import ToolLoopRunner, ToolLoopState


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
