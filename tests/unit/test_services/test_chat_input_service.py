"""Unit tests for shared chat-input preparation service."""

from pathlib import Path

import pytest

from src.api.services.chat_input_service import ChatInputService


class _FakeStorage:
    def __init__(self):
        self.append_calls = []

    async def get_session(self, *_args, **_kwargs):
        return {"state": {"messages": [{"role": "user"}, {"role": "assistant"}]}}

    async def append_message(self, *args, **kwargs):
        self.append_calls.append((args, kwargs))
        return "user-msg-1"


class _FakeFileService:
    def __init__(self):
        self.attachments_dir = Path("/tmp")
        self.read_paths = []
        self.moves = []

    async def get_file_content(self, path):
        self.read_paths.append(path)
        return "file body"

    async def move_to_permanent(self, session_id, message_index, temp_path, filename):
        self.moves.append((session_id, message_index, temp_path, filename))


@pytest.mark.asyncio
async def test_prepare_user_input_handles_attachments_and_append():
    storage = _FakeStorage()
    file_service = _FakeFileService()
    service = ChatInputService(storage=storage, file_service=file_service)

    prepared = await service.prepare_user_input(
        session_id="s1",
        raw_user_message="hello",
        expanded_user_message="hello",
        attachments=[
            {"filename": "note.txt", "temp_path": "tmp-note", "mime_type": "text/plain", "size": 10},
            {"filename": "photo.png", "temp_path": "tmp-photo", "mime_type": "image/png", "size": 20},
        ],
        skip_user_append=False,
        context_type="chat",
        project_id=None,
    )

    assert prepared.raw_user_message == "hello"
    assert "[File 1: note.txt]" in prepared.full_message_content
    assert "file body" in prepared.full_message_content
    assert "[File 2: photo.png]" not in prepared.full_message_content
    assert prepared.user_message_id == "user-msg-1"
    assert len(file_service.moves) == 2
    assert file_service.moves[0] == ("s1", 2, "tmp-note", "note.txt")
    assert file_service.moves[1] == ("s1", 2, "tmp-photo", "photo.png")

    assert len(storage.append_calls) == 1
    _, append_kwargs = storage.append_calls[0]
    assert append_kwargs["attachments"][0]["filename"] == "note.txt"
    assert append_kwargs["attachments"][1]["mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_prepare_user_input_can_skip_user_append():
    storage = _FakeStorage()
    file_service = _FakeFileService()
    service = ChatInputService(storage=storage, file_service=file_service)

    prepared = await service.prepare_user_input(
        session_id="s2",
        raw_user_message="hello",
        expanded_user_message="hello",
        attachments=None,
        skip_user_append=True,
        context_type="chat",
        project_id=None,
    )

    assert prepared.full_message_content == "hello"
    assert prepared.user_message_id is None
    assert storage.append_calls == []
