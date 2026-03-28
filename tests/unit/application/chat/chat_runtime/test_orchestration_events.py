"""Unit tests for orchestration event schema validation."""

import pytest
from pydantic import ValidationError

from src.application.chat.chat_runtime.events import normalize_orchestration_event


def test_normalize_event_accepts_known_event_type():
    payload = {
        "type": "assistant_chunk",
        "chunk": "hello",
        "assistant_id": "a1",
    }
    normalized = normalize_orchestration_event(payload)
    assert normalized["type"] == "assistant_chunk"
    assert normalized["chunk"] == "hello"
    assert normalized["assistant_id"] == "a1"


def test_normalize_event_accepts_tool_diagnostics():
    payload = {
        "type": "tool_diagnostics",
        "assistant_id": "a1",
        "assistant_turn_id": "turn-1",
        "tool_search_count": 2,
        "tool_read_count": 1,
        "tool_finalize_reason": "fallback_empty_answer",
    }

    normalized = normalize_orchestration_event(payload)

    assert normalized["type"] == "tool_diagnostics"
    assert normalized["assistant_id"] == "a1"
    assert normalized["assistant_turn_id"] == "turn-1"
    assert normalized["tool_search_count"] == 2
    assert normalized["tool_read_count"] == 1
    assert normalized["tool_finalize_reason"] == "fallback_empty_answer"


def test_normalize_event_rejects_unknown_type():
    with pytest.raises(ValueError, match="unsupported orchestration event type"):
        normalize_orchestration_event({"type": "unknown_event", "foo": "bar"})


def test_normalize_event_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        normalize_orchestration_event({"type": "model_done", "model_id": "m1"})
