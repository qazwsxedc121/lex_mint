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


def test_extract_memory_candidates_detects_identity_and_preference(memory_service):
    text = "我是一名后端工程师。以后请用中文回答，尽量简短。"

    items = memory_service.extract_memory_candidates(text)

    layers = {item["layer"] for item in items}
    assert "identity" in layers
    assert "preference" in layers


def test_search_memories_for_scopes_merges_and_dedups(memory_service, monkeypatch):
    def fake_search_scope(**kwargs):
        scope = kwargs["scope"]
        if scope == "global":
            return [
                MemoryResult(
                    id="mem_same",
                    content="Use concise replies.",
                    score=0.6,
                    metadata={"scope": "global", "layer": "preference", "hash": "h1"},
                ),
                MemoryResult(
                    id="mem_global",
                    content="User is an engineer.",
                    score=0.7,
                    metadata={"scope": "global", "layer": "identity", "hash": "h2"},
                ),
            ]

        return [
            MemoryResult(
                id="mem_same",
                content="Use concise replies.",
                score=0.9,
                metadata={"scope": "assistant", "layer": "preference", "hash": "h1"},
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


def test_extract_and_persist_from_turn_assigns_scope(memory_service, monkeypatch):
    captured = []

    def fake_upsert_memory(**kwargs):
        captured.append(kwargs)
        return {"id": f"mem_{len(captured)}", **kwargs}

    monkeypatch.setattr(memory_service, "upsert_memory", fake_upsert_memory)

    asyncio.run(
        memory_service.extract_and_persist_from_turn(
            user_message="我是一名数据分析师。以后请用中文回答。",
            assistant_message="收到",
            assistant_id="assistant-a",
            source_session_id="s1",
            source_message_id="m1",
            assistant_memory_enabled=True,
        )
    )

    assert len(captured) >= 2
    identity_item = next(item for item in captured if item["layer"] == "identity")
    preference_item = next(item for item in captured if item["layer"] == "preference")

    assert identity_item["scope"] == "global"
    assert preference_item["scope"] == "assistant"
    assert preference_item["assistant_id"] == "assistant-a"
