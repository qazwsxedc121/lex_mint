"""Unit tests for MemoryService."""

import asyncio

import pytest

from src.api.services.memory_config_service import MemoryConfigService
from src.api.services.memory_service import MemoryResult, MemoryService


@pytest.fixture
def memory_service(temp_config_dir):
    config_path = temp_config_dir / "memory_config.yaml"
    cfg = MemoryConfigService(config_path=str(config_path))
    cfg.save_flat_config({"enabled": True})
    return MemoryService(memory_config_service=cfg)


def test_extract_memory_candidates_returns_empty(memory_service):
    text = "I am a backend engineer. Please respond in Chinese."

    items = memory_service.extract_memory_candidates(text)

    assert items == []


def test_search_memories_for_scopes_merges_and_dedups(memory_service, monkeypatch):
    def fake_search_scope(**kwargs):
        scope = kwargs["scope"]
        if scope == "global":
            return [
                MemoryResult(
                    id="mem_same",
                    content="Use concise replies.",
                    score=0.6,
                    metadata={"scope": "global", "layer": "fact", "hash": "h1"},
                ),
                MemoryResult(
                    id="mem_global",
                    content="User is an engineer.",
                    score=0.7,
                    metadata={"scope": "global", "layer": "fact", "hash": "h2"},
                ),
            ]

        return [
            MemoryResult(
                id="mem_same",
                content="Use concise replies.",
                score=0.9,
                metadata={"scope": "assistant", "layer": "fact", "hash": "h1"},
            )
        ]

    monkeypatch.setattr(memory_service, "_search_scope", fake_search_scope)
    monkeypatch.setattr(memory_service, "_refresh_ids_from_collection", lambda results, _: results)

    items = memory_service.search_memories_for_scopes(
        query="reply style",
        assistant_id="assistant-a",
        include_global=True,
        include_assistant=True,
        limit=10,
    )

    assert len(items) == 2
    assert items[0]["id"] == "mem_same"
    assert items[0]["score"] == pytest.approx(0.9)


def test_extract_and_persist_from_turn_returns_empty(memory_service):
    result = asyncio.run(
        memory_service.extract_and_persist_from_turn(
            user_message="I am a data analyst. Please respond in Chinese.",
            assistant_message="OK",
            assistant_id="assistant-a",
            source_session_id="s1",
            source_message_id="m1",
            assistant_memory_enabled=True,
        )
    )

    assert result == []


def test_build_memory_context_respects_enabled_layers(memory_service, monkeypatch):
    memory_service.memory_config_service.save_flat_config({"enabled_layers": ["instruction"]})

    instruction_calls = {"count": 0}
    fact_calls = {"count": 0}

    def fake_load_instruction_memories(**kwargs):
        _ = kwargs
        instruction_calls["count"] += 1
        return [
            MemoryResult(
                id="mem_instruction",
                content="Respond with concise bullet points.",
                score=None,
                metadata={"scope": "global", "layer": "instruction"},
            )
        ]

    def fake_search_memories_for_scopes(**kwargs):
        _ = kwargs
        fact_calls["count"] += 1
        return [
            {
                "id": "mem_fact",
                "content": "User works in finance.",
                "score": 0.9,
                "scope": "global",
                "layer": "fact",
            }
        ]

    monkeypatch.setattr(memory_service, "_load_instruction_memories", fake_load_instruction_memories)
    monkeypatch.setattr(memory_service, "search_memories_for_scopes", fake_search_memories_for_scopes)

    context, sources = memory_service.build_memory_context(
        query="How should you reply?",
        assistant_id="assistant-a",
    )

    assert instruction_calls["count"] == 1
    assert fact_calls["count"] == 0
    assert "## User instructions (always apply):" in context
    assert "Respond with concise bullet points." in context
    assert "## User context (relevant background):" not in context
    assert [source["layer"] for source in sources] == ["instruction"]
