"""Tests for SiliconFlowAdapter behavior."""

import pytest

from src.providers.adapters.siliconflow_adapter import SiliconFlowAdapter


def test_create_llm_sets_thinking_budget(monkeypatch):
    captured = {}

    class FakeChatReasoningOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "src.providers.adapters.siliconflow_adapter.ChatReasoningOpenAI",
        FakeChatReasoningOpenAI,
    )

    adapter = SiliconFlowAdapter()
    adapter.create_llm(
        model="Qwen/QwQ-32B",
        base_url="https://api.siliconflow.com/v1",
        api_key="k",
        thinking_enabled=True,
        reasoning_effort="high",
    )

    assert captured["extra_body"]["enable_thinking"] is True
    assert captured["extra_body"]["thinking_budget"] == 8192


def test_create_llm_disable_thinking_takes_precedence(monkeypatch):
    captured = {}

    class FakeChatReasoningOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "src.providers.adapters.siliconflow_adapter.ChatReasoningOpenAI",
        FakeChatReasoningOpenAI,
    )

    adapter = SiliconFlowAdapter()
    adapter.create_llm(
        model="Qwen/QwQ-32B",
        base_url="https://api.siliconflow.com/v1",
        api_key="k",
        thinking_enabled=True,
        disable_thinking=True,
    )

    assert captured["extra_body"]["enable_thinking"] is False
    assert "thinking_budget" not in captured["extra_body"]


@pytest.mark.asyncio
async def test_fetch_models_uses_text_filter_and_filters_results(monkeypatch):
    seen = {"params": None, "headers": None}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"id": "Qwen/Qwen2.5-7B-Instruct", "type": "text"},
                    {"id": "black-forest-labs/FLUX.1", "type": "image"},
                ]
            }

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            seen["headers"] = headers
            seen["params"] = params
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    adapter = SiliconFlowAdapter()
    models = await adapter.fetch_models("https://api.siliconflow.com/v1", "test-key")

    assert seen["headers"]["Authorization"] == "Bearer test-key"
    assert seen["params"] == {"type": "text"}
    assert [m["id"] for m in models] == ["Qwen/Qwen2.5-7B-Instruct"]


@pytest.mark.asyncio
async def test_test_connection_returns_auth_error_for_unauthorized(monkeypatch):
    class FakeResponse:
        status_code = 401

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": []}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    adapter = SiliconFlowAdapter()
    ok, message = await adapter.test_connection("https://api.siliconflow.com/v1", "bad-key")

    assert ok is False
    assert "Authentication failed" in message
