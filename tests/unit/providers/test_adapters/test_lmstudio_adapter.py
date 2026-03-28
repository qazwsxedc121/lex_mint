"""Tests for the LM Studio adapter backed by the official SDK."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

from src.providers.adapters.lmstudio_adapter import LmStudioAdapter


class _FakeStats:
    def __init__(self, *, prompt=0, predicted=0, total=0):
        self.prompt_tokens_count = prompt
        self.predicted_tokens_count = predicted
        self.total_tokens_count = total


class _FakeResult:
    def __init__(self, *, content: str, stats: _FakeStats):
        self.content = content
        self.stats = stats


class _FakeFragment:
    def __init__(self, content: str, reasoning_type: str = "none"):
        self.content = content
        self.reasoning_type = reasoning_type


class _FakeStream:
    def __init__(self, fragments, result):
        self._fragments = list(fragments)
        self._result = result

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __aiter__(self):
        async def _iterate():
            for fragment in self._fragments:
                yield fragment

        return _iterate()

    def result(self):
        return self._result


class _FakeModel:
    def __init__(self, *, result=None, stream=None, context_length=4096):
        self._result = result
        self._stream = stream
        self._context_length = context_length
        self.respond_calls = []
        self.stream_calls = []

    async def respond(self, history, *, config=None, **kwargs):
        self.respond_calls.append({"history": history, "config": config, "kwargs": kwargs})
        return self._result

    async def respond_stream(self, history, *, config=None, **kwargs):
        self.stream_calls.append({"history": history, "config": config, "kwargs": kwargs})
        return self._stream

    async def get_context_length(self):
        return self._context_length


class _FakeInfo:
    def __init__(
        self,
        *,
        model_key: str,
        display_name: str,
        vision: bool = False,
        trained_for_tool_use: bool = False,
        max_context_length: int = 4096,
    ):
        self.model_key = model_key
        self.display_name = display_name
        self.vision = vision
        self.trained_for_tool_use = trained_for_tool_use
        self.max_context_length = max_context_length


class _FakeDownloadedModel:
    def __init__(self, info):
        self.info = info


class _FakeLlmSession:
    def __init__(self, *, model=None, downloaded=None, loaded=None):
        self._model = model
        self._downloaded = list(downloaded or [])
        self._loaded = list(loaded or [])

    async def model(self, model_key):
        return self._model

    async def list_downloaded(self):
        return self._downloaded

    async def list_loaded(self):
        return self._loaded


class _FakeAsyncClient:
    def __init__(self, api_host, *, model=None, downloaded=None, loaded=None):
        self.api_host = api_host
        self.llm = _FakeLlmSession(model=model, downloaded=downloaded, loaded=loaded)
        self.prepared_images = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def prepare_image(self, data, name=None):
        handle = {"name": name, "size": len(data)}
        self.prepared_images.append(handle)
        return handle


def test_create_llm_normalizes_base_url_and_reasoning():
    adapter = LmStudioAdapter()

    llm = adapter.create_llm(
        model="qwen3-30b",
        base_url="http://localhost:1234/v1",
        api_key="",
        thinking_enabled=True,
        reasoning_effort="high",
        num_ctx=32768,
    )

    assert llm.api_host == "localhost:1234"
    assert llm.base_url == "localhost:1234"
    assert llm._defaults["reasoning"] == "high"
    assert llm._defaults["context_length"] == 32768


@pytest.mark.asyncio
async def test_invoke_uses_sdk_and_maps_usage(monkeypatch):
    fake_model = _FakeModel(
        result=_FakeResult(content="hello", stats=_FakeStats(prompt=12, predicted=3, total=15))
    )

    monkeypatch.setattr(
        "src.providers.adapters.lmstudio_adapter.lms.AsyncClient",
        lambda api_host: _FakeAsyncClient(api_host, model=fake_model),
    )

    adapter = LmStudioAdapter()
    llm = adapter.create_llm(
        model="qwen3-30b",
        base_url="http://localhost:1234",
        api_key="",
        streaming=False,
    )
    response = await adapter.invoke(llm, [HumanMessage(content="hi")])

    assert response.content == "hello"
    assert response.usage is not None
    assert response.usage.total_tokens == 15
    assert fake_model.respond_calls[0]["config"]["temperature"] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_stream_uses_sdk_and_maps_reasoning_and_usage(monkeypatch):
    result = _FakeResult(content="answer", stats=_FakeStats(prompt=4, predicted=2, total=6))
    stream = _FakeStream(
        [
            _FakeFragment("plan", reasoning_type="reasoning"),
            _FakeFragment("answer"),
        ],
        result,
    )
    fake_model = _FakeModel(stream=stream)

    monkeypatch.setattr(
        "src.providers.adapters.lmstudio_adapter.lms.AsyncClient",
        lambda api_host: _FakeAsyncClient(api_host, model=fake_model),
    )

    adapter = LmStudioAdapter()
    llm = adapter.create_llm(model="qwen3-30b", base_url="localhost:1234", api_key="")
    chunks = [chunk async for chunk in adapter.stream(llm, [HumanMessage(content="hi")])]

    assert [chunk.thinking for chunk in chunks if chunk.thinking] == ["plan"]
    assert [chunk.content for chunk in chunks if chunk.content] == ["answer"]
    assert chunks[-1].usage is not None
    assert chunks[-1].usage.total_tokens == 6
    assert fake_model.stream_calls[0]["config"]["temperature"] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_fetch_models_uses_sdk_downloaded_model_metadata(monkeypatch):
    downloaded = [
        _FakeDownloadedModel(
            _FakeInfo(
                model_key="qwen3-30b",
                display_name="Qwen 3 30B",
                trained_for_tool_use=True,
                max_context_length=32768,
            )
        )
    ]
    loaded = [SimpleNamespace(identifier="qwen3-30b")]

    monkeypatch.setattr(
        "src.providers.adapters.lmstudio_adapter.lms.AsyncClient",
        lambda api_host: _FakeAsyncClient(api_host, downloaded=downloaded, loaded=loaded),
    )

    adapter = LmStudioAdapter()
    models = await adapter.fetch_models("http://localhost:1234", "")

    assert [item["id"] for item in models] == ["qwen3-30b"]
    assert models[0]["name"] == "Qwen 3 30B"
    assert models[0]["capabilities"]["context_length"] == 32768
    assert models[0]["capabilities"]["function_calling"] is True
    assert "loaded" in models[0]["tags"]


@pytest.mark.asyncio
async def test_test_connection_accepts_downloaded_model(monkeypatch):
    downloaded = [_FakeDownloadedModel(_FakeInfo(model_key="qwen3-30b", display_name="Qwen 3 30B"))]
    loaded = []

    monkeypatch.setattr(
        "src.providers.adapters.lmstudio_adapter.lms.AsyncClient",
        lambda api_host: _FakeAsyncClient(api_host, downloaded=downloaded, loaded=loaded),
    )

    adapter = LmStudioAdapter()
    success, message = await adapter.test_connection(
        "http://localhost:1234", "", model_id="qwen3-30b"
    )

    assert success is True
    assert "Connected to LM Studio" in message
