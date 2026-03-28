"""Tests for title generation service behavior."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.application.chat.title_generation_service import (
    TitleGenerationService,
    _response_content_to_text,
)


class _FakeStorage:
    def __init__(self, messages=None):
        self.messages = messages or [
            {"role": "human", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        self.updated = None

    async def get_session(self, session_id: str):
        return {"session_id": session_id, "state": {"messages": list(self.messages)}}

    async def update_session_metadata(self, session_id: str, updates: dict[str, str]):
        self.updated = (session_id, updates)


def test_response_content_to_text_variants():
    assert _response_content_to_text("hello") == "hello"
    assert _response_content_to_text(["a", {"text": "b"}]) == "ab"
    assert _response_content_to_text(None) == ""


def test_should_generate_title_and_save_reload(tmp_path: Path):
    config_path = tmp_path / "title_generation.yaml"
    service = TitleGenerationService(storage=_FakeStorage(), config_path=str(config_path))

    assert service.should_generate_title(2, "New Conversation") is True
    assert service.should_generate_title(2, "Already Good") is False
    assert service.should_generate_title(0, "New Conversation") is False

    service.save_config({"trigger_threshold": 3})
    assert service.config.trigger_threshold == 3
    service.reload_config()
    assert service.config.trigger_threshold == 3


@pytest.mark.asyncio
async def test_generate_title_async_success_timeout_and_empty(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "title_generation.yaml"
    storage = _FakeStorage()
    service = TitleGenerationService(storage=storage, config_path=str(config_path))
    service.save_config(
        {
            "enabled": True,
            "model_id": "provider:model",
            "prompt_template": "Summarize: {conversation_text}",
            "timeout_seconds": 1,
        }
    )

    class _Model:
        async def ainvoke(self, prompt: str):
            assert "User: Hello" in prompt
            return type("Response", (), {"content": '"Short title"'})()

    class _ModelConfigService:
        def get_llm_instance(self, model_id: str):
            assert model_id == "provider:model"
            return _Model()

    monkeypatch.setattr(
        "src.application.chat.title_generation_service.ModelConfigService",
        _ModelConfigService,
    )

    title = await service.generate_title_async("session-1")
    assert title == "Short title"
    assert storage.updated == ("session-1", {"title": "Short title"})

    class _TimeoutModel:
        async def ainvoke(self, prompt: str):
            raise TimeoutError("slow")

    class _TimeoutService:
        def get_llm_instance(self, model_id: str):
            return _TimeoutModel()

    async def _raise_timeout(coro, timeout):
        _ = timeout
        coro.close()
        raise asyncio.TimeoutError()

    monkeypatch.setattr(
        "src.application.chat.title_generation_service.ModelConfigService",
        _TimeoutService,
    )
    monkeypatch.setattr(
        "src.application.chat.title_generation_service.asyncio.wait_for", _raise_timeout
    )
    assert await service.generate_title_async("session-2") is None

    storage_empty = _FakeStorage(messages=[])
    service_empty = TitleGenerationService(
        storage=storage_empty, config_path=str(tmp_path / "empty.yaml")
    )
    assert await service_empty.generate_title_async("session-3") is None
