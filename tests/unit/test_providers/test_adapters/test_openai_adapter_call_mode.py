"""Tests for OpenAIAdapter call_mode and responses fallback behavior."""

from types import SimpleNamespace

import pytest
from langchain_openai import ChatOpenAI

from src.providers.adapters.openai_adapter import OpenAIAdapter
from src.providers.types import CallMode


def test_create_llm_enables_responses_mode(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("src.providers.adapters.openai_adapter.ChatOpenAI", FakeChatOpenAI)

    adapter = OpenAIAdapter()
    adapter.create_llm(
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key="k",
        call_mode=CallMode.RESPONSES,
    )

    assert captured["use_responses_api"] is True


def test_create_llm_defaults_to_chat_completions(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("src.providers.adapters.openai_adapter.ChatOpenAI", FakeChatOpenAI)

    adapter = OpenAIAdapter()
    adapter.create_llm(
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key="k",
        call_mode=CallMode.CHAT_COMPLETIONS,
    )

    assert captured["use_responses_api"] is False


@pytest.mark.asyncio
async def test_invoke_fallback_from_responses_to_chat(monkeypatch):
    adapter = OpenAIAdapter()
    fallback_used = {"value": False}

    class FailingResponsesLLM:
        use_responses_api = True

        async def ainvoke(self, _messages):
            raise RuntimeError("responses endpoint failed")

    class SuccessfulChatLLM:
        use_responses_api = False

        async def ainvoke(self, _messages):
            return SimpleNamespace(content="ok", additional_kwargs={}, response_metadata={})

    def fake_clone(_llm, *, use_responses_api: bool):
        assert use_responses_api is False
        fallback_used["value"] = True
        return SuccessfulChatLLM()

    monkeypatch.setattr(adapter, "_clone_with_mode", fake_clone)

    result = await adapter.invoke(
        FailingResponsesLLM(),
        messages=[SimpleNamespace()],
        allow_responses_fallback=True,
    )

    assert fallback_used["value"] is True
    assert result.content == "ok"


@pytest.mark.asyncio
async def test_stream_fallback_from_responses_to_chat(monkeypatch):
    adapter = OpenAIAdapter()
    fallback_used = {"value": False}

    class FailingResponsesLLM:
        use_responses_api = True

        async def astream(self, _messages):
            raise RuntimeError("responses stream failed")
            yield  # pragma: no cover

    class SuccessfulChatLLM:
        use_responses_api = False

        async def astream(self, _messages):
            yield SimpleNamespace(content="chunk", additional_kwargs={})

    def fake_clone(_llm, *, use_responses_api: bool):
        assert use_responses_api is False
        fallback_used["value"] = True
        return SuccessfulChatLLM()

    monkeypatch.setattr(adapter, "_clone_with_mode", fake_clone)

    chunks = []
    async for chunk in adapter.stream(
        FailingResponsesLLM(),
        messages=[SimpleNamespace()],
        allow_responses_fallback=True,
    ):
        chunks.append(chunk)

    assert fallback_used["value"] is True
    assert [c.content for c in chunks] == ["chunk"]


def test_clone_with_mode_preserves_bound_tools_binding():
    adapter = OpenAIAdapter()

    base_llm = ChatOpenAI(
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key="k",
        use_responses_api=True,
    )
    bound_llm = base_llm.bind_tools([])

    cloned = adapter._clone_with_mode(bound_llm, use_responses_api=False)

    assert getattr(cloned, "use_responses_api", None) is False
    assert getattr(cloned, "kwargs", {}).get("tools") == []
