"""Tests for LocalGgufAdapter GPU defaults and tool parsing."""

import pytest
from langchain_core.messages import HumanMessage

from src.providers.adapters.local_gguf_adapter import LocalGgufAdapter


def test_create_llm_defaults_to_full_gpu_offload(monkeypatch):
    captured = {}

    class FakeLocalLlamaCppService:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.model_path = type("ModelPath", (), {"name": "Qwen3-0.6B-Q8_0.gguf"})()
            self.n_ctx = kwargs["n_ctx"]

    monkeypatch.setattr(
        "src.providers.adapters.local_gguf_adapter.LocalLlamaCppService",
        FakeLocalLlamaCppService,
    )

    adapter = LocalGgufAdapter()
    adapter.create_llm(
        model="models/llm/Qwen3-0.6B-Q8_0.gguf",
        base_url="local://gguf",
        api_key="",
    )

    assert captured["n_gpu_layers"] == -1


def test_create_llm_preserves_explicit_cpu_override(monkeypatch):
    captured = {}

    class FakeLocalLlamaCppService:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.model_path = type("ModelPath", (), {"name": "Qwen3-0.6B-Q8_0.gguf"})()
            self.n_ctx = kwargs["n_ctx"]

    monkeypatch.setattr(
        "src.providers.adapters.local_gguf_adapter.LocalLlamaCppService",
        FakeLocalLlamaCppService,
    )

    adapter = LocalGgufAdapter()
    adapter.create_llm(
        model="models/llm/Qwen3-0.6B-Q8_0.gguf",
        base_url="local://gguf",
        api_key="",
        n_gpu_layers=0,
    )

    assert captured["n_gpu_layers"] == 0


def test_create_llm_passes_disable_thinking_flag(monkeypatch):
    class FakeLocalLlamaCppService:
        def __init__(self, **kwargs):
            self.model_path = type("ModelPath", (), {"name": "Qwen3-0.6B-Q8_0.gguf"})()
            self.n_ctx = kwargs["n_ctx"]

    monkeypatch.setattr(
        "src.providers.adapters.local_gguf_adapter.LocalLlamaCppService",
        FakeLocalLlamaCppService,
    )

    adapter = LocalGgufAdapter()
    llm = adapter.create_llm(
        model="models/llm/Qwen3-0.6B-Q8_0.gguf",
        base_url="local://gguf",
        api_key="",
        disable_thinking=True,
    )

    assert llm._defaults["disable_thinking"] is True


def test_bind_tools_converts_tools_to_openai_schema(monkeypatch):
    class FakeLocalLlamaCppService:
        def __init__(self, **kwargs):
            self.model_path = type("ModelPath", (), {"name": "Qwen3-0.6B-Q8_0.gguf"})()
            self.n_ctx = kwargs["n_ctx"]

    monkeypatch.setattr(
        "src.providers.adapters.local_gguf_adapter.LocalLlamaCppService",
        FakeLocalLlamaCppService,
    )

    adapter = LocalGgufAdapter()
    llm = adapter.create_llm(
        model="models/llm/Qwen3-0.6B-Q8_0.gguf",
        base_url="local://gguf",
        api_key="",
    )
    bound = llm.bind_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "Calculate an expression",
                    "parameters": {
                        "type": "object",
                        "properties": {"expression": {"type": "string"}},
                        "required": ["expression"],
                    },
                },
            }
        ]
    )

    assert len(bound._bound_tools) == 1
    assert bound._bound_tools[0]["function"]["name"] == "calculator"


@pytest.mark.asyncio
async def test_invoke_parses_local_tool_call_xml(monkeypatch):
    class FakeLocalLlamaCppService:
        def __init__(self, **kwargs):
            self.model_path = type("ModelPath", (), {"name": "Qwen3-0.6B-Q8_0.gguf"})()
            self.n_ctx = kwargs["n_ctx"]

        def complete_messages(self, _messages, **kwargs):
            assert kwargs["tools"][0]["function"]["name"] == "calculator"
            assert kwargs["tool_choice"] == "auto"
            return (
                "<think>Need a tool.</think>\n"
                '<tool_call>{"name": "calculator", "arguments": {"expression": "2+3"}}</tool_call>'
            )

    monkeypatch.setattr(
        "src.providers.adapters.local_gguf_adapter.LocalLlamaCppService",
        FakeLocalLlamaCppService,
    )

    adapter = LocalGgufAdapter()
    llm = adapter.create_llm(
        model="models/llm/Qwen3-0.6B-Q8_0.gguf",
        base_url="local://gguf",
        api_key="",
    ).bind_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "Calculate an expression",
                    "parameters": {
                        "type": "object",
                        "properties": {"expression": {"type": "string"}},
                        "required": ["expression"],
                    },
                },
            }
        ]
    )

    response = await adapter.invoke(llm, [HumanMessage(content="2+3")])

    assert response.content == ""
    assert response.thinking == "Need a tool."
    assert response.tool_calls[0]["name"] == "calculator"
    assert response.tool_calls[0]["args"] == {"expression": "2+3"}


@pytest.mark.asyncio
async def test_stream_parses_tool_call_and_hides_thinking_when_disabled(monkeypatch):
    class FakeLocalLlamaCppService:
        def __init__(self, **kwargs):
            self.model_path = type("ModelPath", (), {"name": "Qwen3-0.6B-Q8_0.gguf"})()
            self.n_ctx = kwargs["n_ctx"]

        def complete_messages(self, _messages, **kwargs):
            return (
                "<think>Need a tool.</think>\n"
                '<tool_call>{"name": "calculator", "arguments": {"expression": "2+3"}}</tool_call>'
            )

    monkeypatch.setattr(
        "src.providers.adapters.local_gguf_adapter.LocalLlamaCppService",
        FakeLocalLlamaCppService,
    )

    adapter = LocalGgufAdapter()
    llm = adapter.create_llm(
        model="models/llm/Qwen3-0.6B-Q8_0.gguf",
        base_url="local://gguf",
        api_key="",
        disable_thinking=True,
    ).bind_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "Calculate an expression",
                    "parameters": {
                        "type": "object",
                        "properties": {"expression": {"type": "string"}},
                        "required": ["expression"],
                    },
                },
            }
        ]
    )

    chunks = [chunk async for chunk in adapter.stream(llm, [HumanMessage(content="2+3")])]

    assert len(chunks) == 1
    assert chunks[0].thinking == ""
    assert chunks[0].tool_calls[0]["name"] == "calculator"
    assert getattr(chunks[0].raw, "tool_calls", [])[0]["name"] == "calculator"
