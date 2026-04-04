"""Tests for session import helpers."""

from __future__ import annotations

from typing import Any

import pytest

from src.application.chat.chatgpt_import_service import ChatGPTImportService
from src.application.chat.markdown_import_service import MarkdownImportService


class _FakeStorage:
    def __init__(self):
        self.calls: list[tuple[str, Any]] = []

    async def create_session(self, **kwargs):
        self.calls.append(("create_session", kwargs))
        return "session-1"

    async def set_messages(self, session_id: str, messages: list[dict[str, Any]], **kwargs):
        self.calls.append(
            ("set_messages", {"session_id": session_id, "messages": messages, **kwargs})
        )

    async def update_session_metadata(self, session_id: str, updates: dict[str, Any], **kwargs):
        self.calls.append(
            ("update_metadata", {"session_id": session_id, "updates": updates, **kwargs})
        )


@pytest.mark.asyncio
async def test_chatgpt_import_service_imports_and_skips_empty_conversations():
    storage = _FakeStorage()
    service = ChatGPTImportService(storage)

    payload = [
        {
            "id": "conv-1",
            "title": "",
            "current_node": "n2",
            "mapping": {
                "n1": {
                    "id": "n1",
                    "parent": None,
                    "message": {
                        "id": "m1",
                        "author": {"role": "user"},
                        "content": {"parts": ["Hello there"]},
                        "create_time": 1700000000,
                    },
                },
                "n2": {
                    "id": "n2",
                    "parent": "n1",
                    "message": {
                        "id": "m2",
                        "author": {"role": "assistant"},
                        "content": {"parts": [{"text": "Hi!"}]},
                        "create_time": 1700000100,
                    },
                },
            },
        },
        {"id": "conv-2", "mapping": {}},
    ]

    result = await service.import_conversations(payload)

    assert result["imported"] == 1
    assert result["skipped"] == 1
    assert result["sessions"][0]["message_count"] == 2
    assert storage.calls[1][1]["messages"][0]["content"] == "Hello there"


def test_chatgpt_import_service_extracts_latest_node_and_content_variants():
    service = ChatGPTImportService(_FakeStorage())

    mapping = {
        "n1": {"message": {"create_time": 1}},
        "n2": {"message": {"create_time": 3}},
        "n3": {"message": {"create_time": 2}},
    }
    assert service._find_latest_node(mapping) == "n2"
    assert (
        service._extract_content_text({"parts": ["a", {"text": "b"}, {"content": "c"}]})
        == "a\nb\nc"
    )
    assert service._extract_title({"title": ""}, [{"role": "user", "content": "x" * 80}]).endswith(
        "..."
    )


@pytest.mark.asyncio
async def test_markdown_import_service_parses_sections_and_title():
    storage = _FakeStorage()
    service = MarkdownImportService(storage)

    result = await service.import_markdown(
        "# Demo\n## User\nHello\n---\n## Assistant\nHi there\n",
        filename="demo.md",
    )
    assert result["imported"] == 1
    assert result["sessions"][0]["title"] == "Demo"

    title, messages = service._parse_markdown(
        "## User\nHello\n## Assistant\nHi\n",
        filename="fallback.md",
    )
    assert title == "fallback"
    assert messages == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    empty = await service.import_markdown("no roles here", filename="empty.md")
    assert empty["imported"] == 0
