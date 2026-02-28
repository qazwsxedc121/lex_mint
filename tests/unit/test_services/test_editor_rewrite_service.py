"""Unit tests for inline editor rewrite service."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.api.services.editor_rewrite_service import EditorRewriteService


class _FakeStorage:
    def __init__(self, session_payload):
        self._session_payload = session_payload

    async def get_session(self, *_args, **_kwargs):
        return self._session_payload


@pytest.mark.asyncio
async def test_stream_rewrite_filters_think_tags_and_uses_overrides(monkeypatch):
    captured_kwargs = {}

    async def fake_call_llm_stream(*_args, **kwargs):
        captured_kwargs.update(kwargs)
        yield "<think>internal"
        yield " hidden</think>Hello"
        yield " world"
        yield {"type": "usage"}

    class FakeAssistantConfigService:
        async def get_assistant(self, _assistant_id: str):
            return SimpleNamespace(
                model_id="provider:assistant-model",
                system_prompt="assistant-system",
                temperature=0.2,
                max_tokens=2048,
                top_p=None,
                top_k=None,
                frequency_penalty=None,
                presence_penalty=None,
            )

    monkeypatch.setattr("src.api.services.editor_rewrite_service.call_llm_stream", fake_call_llm_stream)
    monkeypatch.setattr(
        "src.api.services.editor_rewrite_service.AssistantConfigService",
        FakeAssistantConfigService,
    )

    service = EditorRewriteService(
        storage=_FakeStorage(
            {
                "assistant_id": "assistant-1",
                "model_id": "provider:session-model",
                "param_overrides": {
                    "model_id": "provider:override-model",
                    "temperature": 0.5,
                },
            }
        )
    )

    chunks = []
    async for chunk in service.stream_rewrite(
        session_id="session-1",
        selected_text="Original text",
        instruction="Make it concise",
        context_before="Before",
        context_after="After",
        file_path="doc.txt",
        language="text",
        context_type="project",
        project_id="proj-1",
    ):
        chunks.append(chunk)

    assert "".join(chunks) == "Hello world"
    assert captured_kwargs["model_id"] == "provider:override-model"
    assert captured_kwargs["temperature"] == 0.5
    assert captured_kwargs["max_tokens"] == 2048
    assert captured_kwargs["reasoning_effort"] == "none"
    assert "assistant-system" in captured_kwargs["system_prompt"]
    assert "Output only the rewritten text." in captured_kwargs["system_prompt"]
    assert captured_kwargs["messages"][0]["role"] == "user"
    assert "<selected_text>" in captured_kwargs["messages"][0]["content"]


@pytest.mark.asyncio
async def test_stream_rewrite_requires_resolved_model():
    service = EditorRewriteService(
        storage=_FakeStorage(
            {
                "assistant_id": None,
                "model_id": "",
                "param_overrides": {},
            }
        )
    )

    with pytest.raises(ValueError, match="Session model is unavailable"):
        async for _ in service.stream_rewrite(
            session_id="session-2",
            selected_text="Text",
            instruction=None,
            context_before="",
            context_after="",
            file_path=None,
            language=None,
            context_type="project",
            project_id="proj-2",
        ):
            pass
