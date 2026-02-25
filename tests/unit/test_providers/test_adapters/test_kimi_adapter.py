"""Tests for KimiAdapter behavior."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.providers.adapters.kimi_adapter import ChatKimiOpenAI, KimiAdapter


def test_create_llm_normalizes_k2_5_params(monkeypatch):
    captured = {}

    class FakeChatKimiOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "src.providers.adapters.kimi_adapter.ChatKimiOpenAI",
        FakeChatKimiOpenAI,
    )

    adapter = KimiAdapter()
    adapter.create_llm(
        model="kimi-k2.5",
        base_url="https://api.moonshot.cn/v1",
        api_key="k",
        temperature=0.2,
        thinking_enabled=True,
        top_p=0.3,
        frequency_penalty=0.5,
        presence_penalty=0.6,
        tool_choice="required",
        n=3,
    )

    assert captured["temperature"] == 1.0
    assert captured["extra_body"]["thinking"] == {"type": "enabled"}
    assert captured["model_kwargs"]["top_p"] == 0.95
    assert captured["model_kwargs"]["frequency_penalty"] == 0.0
    assert captured["model_kwargs"]["presence_penalty"] == 0.0
    assert captured["model_kwargs"]["tool_choice"] == "auto"
    assert captured["model_kwargs"]["n"] == 1


def test_create_llm_disable_thinking_takes_precedence(monkeypatch):
    captured = {}

    class FakeChatKimiOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "src.providers.adapters.kimi_adapter.ChatKimiOpenAI",
        FakeChatKimiOpenAI,
    )

    adapter = KimiAdapter()
    adapter.create_llm(
        model="kimi-k2.5",
        base_url="https://api.moonshot.cn/v1",
        api_key="k",
        temperature=1.0,
        thinking_enabled=True,
        disable_thinking=True,
    )

    assert captured["extra_body"]["thinking"] == {"type": "disabled"}
    assert captured["temperature"] == 0.6


@pytest.mark.asyncio
async def test_fetch_models_appends_v1_and_parses_response(monkeypatch):
    seen = {"url": None, "headers": None}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"id": "kimi-k2.5", "name": "Kimi K2.5"},
                    {"id": "kimi-k2-turbo-preview"},
                ]
            }

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            seen["url"] = url
            seen["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    adapter = KimiAdapter()
    models = await adapter.fetch_models("https://api.moonshot.cn", "test-key")

    assert seen["url"] == "https://api.moonshot.cn/v1/models"
    assert seen["headers"] == {"Authorization": "Bearer test-key"}
    assert [m["id"] for m in models] == ["kimi-k2-turbo-preview", "kimi-k2.5"]


@pytest.mark.asyncio
async def test_fetch_models_returns_empty_list_on_error(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            raise RuntimeError("boom")

    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    adapter = KimiAdapter()
    models = await adapter.fetch_models("https://api.moonshot.cn/v1", "test-key")

    assert models == []


@pytest.mark.asyncio
async def test_test_connection_returns_auth_error_for_unauthorized(monkeypatch):
    class FakeResponse:
        status_code = 401

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    adapter = KimiAdapter()
    ok, message = await adapter.test_connection("https://api.moonshot.cn/v1", "bad-key")

    assert ok is False
    assert "Authentication failed" in message


def test_chat_kimi_payload_keeps_reasoning_content_for_tool_call_messages():
    llm = ChatKimiOpenAI(
        model="kimi-k2.5",
        base_url="https://api.moonshot.cn/v1",
        api_key="k",
        use_responses_api=False,
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


def test_chat_kimi_payload_skips_reasoning_when_interleaved_not_required():
    llm = ChatKimiOpenAI(
        model="kimi-k2.5",
        base_url="https://api.moonshot.cn/v1",
        api_key="k",
        use_responses_api=False,
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
