"""Unit tests for session application service."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.chat import SessionApplicationDeps, SessionApplicationService


def _build_service(tmp_path: Path):
    storage = AsyncMock()
    assistant_service = AsyncMock()
    model_service = AsyncMock()
    attachments_dir = tmp_path / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    file_service = SimpleNamespace(attachments_dir=attachments_dir)
    service = SessionApplicationService(
        SessionApplicationDeps(
            storage=storage,
            assistant_service=assistant_service,
            model_service=model_service,
            file_service=file_service,
        )
    )
    return service, storage, assistant_service, model_service, attachments_dir


async def test_create_session_normalizes_group_participants_and_settings(tmp_path: Path):
    service, storage, assistant_service, model_service, _ = _build_service(tmp_path)
    storage.create_session.return_value = "session-1"
    assistant_service.require_enabled_assistant.return_value = object()
    model_service.require_enabled_model.return_value = (object(), object())

    session_id = await service.create_session(
        assistant_id="default",
        model_id=None,
        target_type=None,
        temporary=False,
        group_assistants=[
            " assistant::writer ",
            "model::openai:gpt-4o",
            "writer",
            " model::openai:gpt-4o ",
        ],
        group_mode="committee",
        group_settings={
            "committee": {
                "policy": {"max_rounds": "8"},
                "actions": {"allow_finish": False},
            },
            "ignored": True,
        },
    )

    assert session_id == "session-1"
    assistant_service.require_enabled_assistant.assert_awaited_once_with("writer")
    model_service.require_enabled_model.assert_awaited_once_with("openai:gpt-4o")
    storage.create_session.assert_awaited_once_with(
        model_id=None,
        assistant_id="default",
        target_type="assistant",
        context_type="chat",
        project_id=None,
        temporary=False,
        group_assistants=["writer", "model::openai:gpt-4o"],
        group_mode="committee",
        group_settings={
            "version": 1,
            "committee": {
                "policy": {"max_rounds": 8},
                "actions": {"allow_finish": False},
            },
        },
    )


async def test_update_param_overrides_validates_model_and_persists(tmp_path: Path):
    service, storage, _, model_service, _ = _build_service(tmp_path)
    model_service.require_enabled_model.return_value = (object(), object())

    await service.update_param_overrides(
        session_id="session-1",
        overrides={
            "model_id": "openai:gpt-4o",
            "temperature": 1.2,
            "max_rounds": 4,
        },
        context_type="project",
        project_id="proj-1",
    )

    model_service.require_enabled_model.assert_awaited_once_with("openai:gpt-4o")
    storage.update_session_metadata.assert_awaited_once_with(
        "session-1",
        {
            "param_overrides": {
                "model_id": "openai:gpt-4o",
                "temperature": 1.2,
                "max_rounds": 4,
            }
        },
        context_type="project",
        project_id="proj-1",
    )


async def test_update_param_overrides_rejects_invalid_keys(tmp_path: Path):
    service, storage, _, model_service, _ = _build_service(tmp_path)

    with pytest.raises(ValueError, match="Invalid override keys"):
        await service.update_param_overrides(
            session_id="session-1",
            overrides={"bogus": 1},
        )

    model_service.require_enabled_model.assert_not_awaited()
    storage.update_session_metadata.assert_not_awaited()


async def test_branch_session_truncates_messages_and_sets_branch_title(tmp_path: Path):
    service, storage, _, _, _ = _build_service(tmp_path)
    storage.get_session.return_value = {
        "assistant_id": "default",
        "model_id": "deepseek:deepseek-chat",
        "title": "Original Chat",
        "state": {
            "messages": [
                {"message_id": "m1", "content": "first"},
                {"message_id": "m2", "content": "second"},
                {"message_id": "m3", "content": "third"},
            ]
        },
    }
    storage.create_session.return_value = "branch-1"

    new_session_id = await service.branch_session(session_id="session-1", message_id="m2")

    assert new_session_id == "branch-1"
    storage.create_session.assert_awaited_once_with(
        model_id="deepseek:deepseek-chat",
        assistant_id="default",
        context_type="chat",
        project_id=None,
    )
    storage.update_session_metadata.assert_awaited_once_with(
        "branch-1",
        {"title": "Original Chat (Branch)"},
        context_type="chat",
        project_id=None,
    )
    storage.set_messages.assert_awaited_once_with(
        "branch-1",
        [
            {"message_id": "m1", "content": "first"},
            {"message_id": "m2", "content": "second"},
        ],
        context_type="chat",
        project_id=None,
    )


async def test_copy_session_copies_attachments_without_temp_directory(tmp_path: Path):
    service, storage, _, _, attachments_dir = _build_service(tmp_path)
    storage.copy_session.return_value = "copy-1"

    source_dir = attachments_dir / "session-1"
    (source_dir / "0").mkdir(parents=True, exist_ok=True)
    (source_dir / "nested").mkdir(parents=True, exist_ok=True)
    (source_dir / "temp").mkdir(parents=True, exist_ok=True)
    (source_dir / "0" / "note.txt").write_text("note", encoding="utf-8")
    (source_dir / "nested" / "image.txt").write_text("image", encoding="utf-8")
    (source_dir / "temp" / "ignore.txt").write_text("ignore", encoding="utf-8")

    new_session_id = await service.copy_session(
        session_id="session-1",
        source_context_type="chat",
        target_context_type="project",
        target_project_id="proj-1",
    )

    assert new_session_id == "copy-1"
    storage.copy_session.assert_awaited_once_with(
        "session-1",
        source_context_type="chat",
        source_project_id=None,
        target_context_type="project",
        target_project_id="proj-1",
    )
    assert (attachments_dir / "copy-1" / "0" / "note.txt").read_text(encoding="utf-8") == "note"
    assert (attachments_dir / "copy-1" / "nested" / "image.txt").read_text(encoding="utf-8") == "image"
    assert not (attachments_dir / "copy-1" / "temp").exists()
