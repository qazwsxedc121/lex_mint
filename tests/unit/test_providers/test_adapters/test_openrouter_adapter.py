"""Tests for OpenRouterAdapter behavior."""

from src.providers.adapters.openrouter_adapter import OpenRouterAdapter


def test_create_llm_sets_openrouter_reasoning_effort(monkeypatch):
    captured = {}

    class FakeChatOpenRouter:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "src.providers.adapters.openrouter_adapter.ChatOpenRouter",
        FakeChatOpenRouter,
    )

    adapter = OpenRouterAdapter()
    adapter.create_llm(
        model="deepseek/deepseek-chat",
        base_url="https://openrouter.ai/api/v1",
        api_key="k",
        thinking_enabled=True,
        reasoning_option="high",
    )

    assert captured["extra_body"]["reasoning"] == {"effort": "high"}


def test_create_llm_uses_interleaved_wrapper_when_required(monkeypatch):
    class FakeChatOpenRouter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeChatOpenRouterInterleaved(FakeChatOpenRouter):
        pass

    monkeypatch.setattr(
        "src.providers.adapters.openrouter_adapter.ChatOpenRouter",
        FakeChatOpenRouter,
    )
    monkeypatch.setattr(
        "src.providers.adapters.openrouter_adapter.ChatOpenRouterInterleaved",
        FakeChatOpenRouterInterleaved,
    )

    adapter = OpenRouterAdapter()
    llm = adapter.create_llm(
        model="moonshotai/kimi-k2.5",
        base_url="https://openrouter.ai/api/v1",
        api_key="k",
        requires_interleaved_thinking=True,
    )

    assert isinstance(llm, FakeChatOpenRouterInterleaved)
    assert getattr(llm, "_requires_interleaved_thinking") is True


def test_create_llm_falls_back_when_openrouter_package_missing(monkeypatch):
    fallback_called = {"value": False}

    def fake_super_create_llm(self, *args, **kwargs):
        fallback_called["value"] = True
        return object()

    monkeypatch.setattr(
        "src.providers.adapters.openrouter_adapter.ChatOpenRouter",
        None,
    )
    monkeypatch.setattr(
        "src.providers.adapters.openrouter_adapter.OpenAIAdapter.create_llm",
        fake_super_create_llm,
    )

    adapter = OpenRouterAdapter()
    adapter.create_llm(
        model="openai/gpt-4o-mini",
        base_url="https://openrouter.ai/api/v1",
        api_key="k",
    )

    assert fallback_called["value"] is True
