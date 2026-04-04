"""Router tests for session management endpoints."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from src.api.routers import sessions as sessions_router


class _FakeUploadFile:
    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self._data = data

    async def read(self) -> bytes:
        return self._data


class _FakeStorage:
    def __init__(self):
        self.calls: list[tuple[str, Any]] = []
        self.session = {
            "title": 'Demo "Session"',
            "state": {
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "<think>reason</think>done"},
                ]
            },
        }

    async def list_sessions(self, **kwargs):
        self.calls.append(("list", kwargs))
        return [{"session_id": "s1", "title": "One"}]

    async def search_sessions(self, query: str, **kwargs):
        self.calls.append(("search", {"query": query, **kwargs}))
        return [{"session_id": "s1", "title": "One"}]

    async def get_session(self, session_id: str, **kwargs):
        self.calls.append(("get", {"session_id": session_id, **kwargs}))
        if session_id == "missing":
            raise FileNotFoundError
        return dict(self.session)

    async def create_session(self, **kwargs):
        self.calls.append(("create_session", kwargs))
        return "imported-session"

    async def set_messages(self, session_id: str, messages: list[dict[str, Any]], **kwargs):
        self.calls.append(
            ("set_messages", {"session_id": session_id, "messages": messages, **kwargs})
        )

    async def update_session_metadata(self, session_id: str, updates: dict[str, Any], **kwargs):
        self.calls.append(
            ("update_metadata", {"session_id": session_id, "updates": updates, **kwargs})
        )

    async def _find_session_file(
        self,
        session_id: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> Path | None:
        _ = session_id, context_type, project_id
        return Path("session.md")


class _FakeSessionService:
    def __init__(self):
        self.calls: list[tuple[str, Any]] = []
        self.fail_with: Exception | None = None

    async def _maybe_fail(self):
        if self.fail_with is not None:
            raise self.fail_with

    async def create_session(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("create_session", kwargs))
        return "session-123"

    async def delete_session(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("delete_session", kwargs))

    async def save_temporary_session(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("save_temporary_session", kwargs))

    async def update_session_target(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("update_session_target", kwargs))

    async def update_group_assistants(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("update_group_assistants", kwargs))

    async def get_group_settings(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("get_group_settings", kwargs))
        return {"group_mode": "committee"}

    async def update_group_settings(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("update_group_settings", kwargs))
        return {"group_mode": kwargs["group_mode"]}

    async def update_session_title(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("update_session_title", kwargs))

    async def update_param_overrides(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("update_param_overrides", kwargs))

    async def branch_session(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("branch_session", kwargs))
        return "branched-session"

    async def duplicate_session(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("duplicate_session", kwargs))
        return "duplicated-session"

    async def move_session(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("move_session", kwargs))

    async def copy_session(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("copy_session", kwargs))
        return "copied-session"

    async def update_session_folder(self, **kwargs):
        await self._maybe_fail()
        self.calls.append(("update_session_folder", kwargs))


@pytest.mark.asyncio
async def test_session_router_create_list_search_get_and_delete(monkeypatch):
    storage = _FakeStorage()
    service = _FakeSessionService()

    create_response = await sessions_router.create_session(
        request=sessions_router.CreateSessionRequest(
            assistant_id="assistant-1",
            target_type="assistant",
            temporary=True,
        ),
        session_service=service,
    )
    assert create_response == {"session_id": "session-123"}

    list_response = await sessions_router.list_sessions(storage=storage)
    assert list_response["sessions"][0]["session_id"] == "s1"

    search_response = await sessions_router.search_sessions(q="demo", storage=storage)
    assert search_response["results"][0]["title"] == "One"

    class _ComparisonStorage:
        def __init__(self, _storage):
            self.storage = _storage

        async def load(self, *args, **kwargs):
            return {"baseline": "A", "candidate": "B"}

    monkeypatch.setattr(sessions_router, "ComparisonStorage", _ComparisonStorage)
    get_response = await sessions_router.get_session(session_id="session-123", storage=storage)
    assert get_response["compare_data"]["baseline"] == "A"

    delete_response = await sessions_router.delete_session(
        session_id="session-123", session_service=service
    )
    assert delete_response["message"] == "Session deleted"


@pytest.mark.asyncio
async def test_session_router_updates_and_transfers():
    service = _FakeSessionService()

    await sessions_router.save_temporary_session(session_id="s1", session_service=service)
    await sessions_router.update_session_model(
        session_id="s1",
        request=sessions_router.UpdateModelRequest(model_id="provider:model"),
        session_service=service,
    )
    await sessions_router.update_session_assistant(
        session_id="s1",
        request=sessions_router.UpdateAssistantRequest(assistant_id="writer"),
        session_service=service,
    )
    target_response = await sessions_router.update_session_target(
        session_id="s1",
        request=sessions_router.UpdateTargetRequest(
            target_type="assistant",
            assistant_id="analyst",
        ),
        session_service=service,
    )
    assert target_response["message"] == "Session target updated successfully"

    group_response = await sessions_router.update_group_assistants(
        session_id="s1",
        request=sessions_router.UpdateGroupAssistantsRequest(group_assistants=["a", "b"]),
        session_service=service,
    )
    assert group_response["message"] == "Group assistants updated"

    settings_response = await sessions_router.get_group_settings(
        session_id="s1", session_service=service
    )
    assert settings_response["group_mode"] == "committee"

    updated_settings = await sessions_router.update_group_settings(
        session_id="s1",
        request=sessions_router.UpdateGroupSettingsRequest(group_mode="round_robin"),
        session_service=service,
    )
    assert updated_settings["group_mode"] == "round_robin"

    title_response = await sessions_router.update_session_title(
        session_id="s1",
        request=sessions_router.UpdateTitleRequest(title="Better"),
        session_service=service,
    )
    assert title_response["message"] == "Title updated successfully"

    overrides_response = await sessions_router.update_param_overrides(
        session_id="s1",
        request=sessions_router.UpdateParamOverridesRequest(param_overrides={"temperature": 0.1}),
        session_service=service,
    )
    assert overrides_response["message"] == "Parameter overrides updated"

    branch_response = await sessions_router.branch_session(
        session_id="s1",
        request=sessions_router.BranchSessionRequest(message_id="m2"),
        session_service=service,
    )
    assert branch_response["session_id"] == "branched-session"

    duplicate_response = await sessions_router.duplicate_session(
        session_id="s1", session_service=service
    )
    assert duplicate_response["session_id"] == "duplicated-session"

    move_response = await sessions_router.move_session(
        session_id="s1",
        request=sessions_router.TransferSessionRequest(
            target_context_type="project", target_project_id="p1"
        ),
        session_service=service,
    )
    assert move_response["message"] == "Session moved successfully"

    copy_response = await sessions_router.copy_session(
        session_id="s1",
        request=sessions_router.TransferSessionRequest(target_context_type="chat"),
        session_service=service,
    )
    assert copy_response["session_id"] == "copied-session"

    await sessions_router.update_session_folder(
        session_id="s1",
        request={"folder_id": "folder-1"},
        session_service=service,
    )


@pytest.mark.asyncio
async def test_session_router_export_and_format_helpers():
    storage = _FakeStorage()

    markdown = sessions_router._build_export_markdown(storage.session)
    assert "<details>" in markdown
    assert "## Assistant" in markdown

    response = await sessions_router.export_session(session_id="s1", storage=storage)
    assert response.media_type == "text/markdown; charset=utf-8"
    assert "Demo%20_Session_.md" in response.headers["Content-Disposition"]


@pytest.mark.asyncio
async def test_session_router_imports_chatgpt_json_zip_and_markdown():
    storage = _FakeStorage()
    payload = [
        {
            "title": "Imported",
            "current_node": "n2",
            "mapping": {
                "n1": {
                    "id": "n1",
                    "parent": None,
                    "message": {
                        "id": "m1",
                        "author": {"role": "user"},
                        "content": {"parts": ["hello"]},
                    },
                },
                "n2": {
                    "id": "n2",
                    "parent": "n1",
                    "message": {
                        "id": "m2",
                        "author": {"role": "assistant"},
                        "content": {"parts": ["hi"]},
                    },
                },
            },
        }
    ]

    json_file = _FakeUploadFile("conversations.json", json.dumps(payload).encode("utf-8"))
    json_response = await sessions_router.import_chatgpt_conversations(
        file=json_file, storage=storage
    )
    assert json_response["imported"] == 1

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("nested/conversations.json", json.dumps(payload))
    zip_response = await sessions_router.import_chatgpt_conversations(
        file=_FakeUploadFile("export.zip", archive.getvalue()),
        storage=storage,
    )
    assert zip_response["imported"] == 1

    markdown_response = await sessions_router.import_markdown_conversation(
        file=_FakeUploadFile("chat.md", b"# Title\n## User\nHello\n## Assistant\nHi\n"),
        storage=storage,
    )
    assert markdown_response["imported"] == 1


@pytest.mark.asyncio
async def test_session_router_maps_validation_and_not_found_errors():
    storage = _FakeStorage()
    service = _FakeSessionService()

    with pytest.raises(HTTPException) as exc_info:
        await sessions_router.create_session(
            request=None,
            context_type="project",
            project_id=None,
            session_service=service,
        )
    assert exc_info.value.status_code == 400

    service.fail_with = ValueError("bad input")
    with pytest.raises(HTTPException) as exc_info:
        await sessions_router.update_session_title(
            session_id="s1",
            request=sessions_router.UpdateTitleRequest(title="bad"),
            session_service=service,
        )
    assert exc_info.value.status_code == 400

    service.fail_with = FileNotFoundError()
    with pytest.raises(HTTPException) as exc_info:
        await sessions_router.delete_session(session_id="missing", session_service=service)
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await sessions_router.get_session(session_id="missing", storage=storage)
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await sessions_router.move_session(
            session_id="s1",
            request=sessions_router.TransferSessionRequest(target_context_type="project"),
            session_service=_FakeSessionService(),
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await sessions_router.copy_session(
            session_id="s1",
            request=sessions_router.TransferSessionRequest(target_context_type="invalid"),
            session_service=_FakeSessionService(),
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await sessions_router.import_chatgpt_conversations(
            file=_FakeUploadFile("bad.txt", b"nope"),
            storage=_FakeStorage(),
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await sessions_router.import_markdown_conversation(
            file=_FakeUploadFile("bad.txt", b"# nope"),
            storage=_FakeStorage(),
        )
    assert exc_info.value.status_code == 400
