"""Tests for DeepSeek adapter interleaved thinking behavior."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.providers.adapters.deepseek_adapter import ChatDeepSeekInterleaved, DeepSeekAdapter


def test_create_llm_returns_interleaved_wrapper():
    adapter = DeepSeekAdapter()
    llm = adapter.create_llm(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key="k",
        streaming=False,
    )

    assert isinstance(llm, ChatDeepSeekInterleaved)


def test_deepseek_payload_keeps_reasoning_content_for_tool_call_messages():
    llm = ChatDeepSeekInterleaved(
        model="deepseek-chat",
        api_key="k",
        api_base="https://api.deepseek.com",
        streaming=False,
    )
    object.__setattr__(llm, "_requires_interleaved_thinking", True)

    messages = [
        HumanMessage(content="What is 1+1?"),
        AIMessage(
            content="",
            tool_calls=[{"name": "simple_calculator", "args": {"expression": "1+1"}, "id": "call_1"}],
            additional_kwargs={"reasoning_content": "I should calculate first."},
        ),
        ToolMessage(content="2", tool_call_id="call_1"),
    ]

    payload = llm._get_request_payload(messages)
    assistant_payload = payload["messages"][1]

    assert assistant_payload["role"] == "assistant"
    assert "tool_calls" in assistant_payload
    assert assistant_payload["reasoning_content"] == "I should calculate first."


def test_deepseek_payload_skips_reasoning_when_interleaved_not_required():
    llm = ChatDeepSeekInterleaved(
        model="deepseek-chat",
        api_key="k",
        api_base="https://api.deepseek.com",
        streaming=False,
    )
    object.__setattr__(llm, "_requires_interleaved_thinking", False)

    messages = [
        HumanMessage(content="What is 1+1?"),
        AIMessage(
            content="",
            tool_calls=[{"name": "simple_calculator", "args": {"expression": "1+1"}, "id": "call_1"}],
            additional_kwargs={"reasoning_content": "I should calculate first."},
        ),
        ToolMessage(content="2", tool_call_id="call_1"),
    ]

    payload = llm._get_request_payload(messages)
    assistant_payload = payload["messages"][1]

    assert assistant_payload["role"] == "assistant"
    assert "tool_calls" in assistant_payload
    assert "reasoning_content" not in assistant_payload
