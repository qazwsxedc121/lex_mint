"""Unit tests for orchestration event schema validation."""

import pytest

from src.api.services.orchestration.events import normalize_orchestration_event


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


def test_normalize_event_rejects_unknown_type():
    with pytest.raises(ValueError, match="unsupported orchestration event type"):
        normalize_orchestration_event({"type": "unknown_event", "foo": "bar"})


def test_normalize_event_rejects_missing_required_fields():
    with pytest.raises(Exception):
        normalize_orchestration_event({"type": "model_done", "model_id": "m1"})

