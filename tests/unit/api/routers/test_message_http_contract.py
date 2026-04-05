"""HTTP-level contract tests for message mutation routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.routers import chat as chat_router
from src.api.routers import sessions as sessions_router


class _FakeChatService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def delete_message(self, **kwargs):
        self.calls.append(("delete_message", kwargs))
        if kwargs.get("message_id") == "missing":
            raise FileNotFoundError()
        if kwargs.get("message_id") == "bad" or kwargs.get("message_index") == -1:
            raise ValueError("bad message")
        if kwargs.get("message_id") == "boom":
            raise RuntimeError("boom")


def _build_client(fake_chat_service: _FakeChatService) -> TestClient:
    app = FastAPI()
    app.include_router(chat_router.router)
    app.include_router(sessions_router.router)
    app.dependency_overrides[chat_router.get_chat_application_service] = lambda: fake_chat_service
    return TestClient(app)


def test_delete_message_contract_uses_chat_route():
    fake_chat_service = _FakeChatService()
    client = _build_client(fake_chat_service)

    response = client.request(
        "DELETE",
        "/api/chat/message?context_type=chat",
        json={"session_id": "s1", "message_id": "m1"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert fake_chat_service.calls == [
        (
            "delete_message",
            {
                "session_id": "s1",
                "message_id": "m1",
                "context_type": "chat",
                "project_id": None,
            },
        )
    ]


def test_delete_message_rejects_legacy_sessions_messages_path():
    fake_chat_service = _FakeChatService()
    client = _build_client(fake_chat_service)

    response = client.request(
        "DELETE",
        "/api/sessions/s1/messages/m1?context_type=chat",
    )

    assert response.status_code in {404, 405}


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"session_id": "s1", "message_id": "missing"}, 404),
        ({"session_id": "s1", "message_id": "bad"}, 400),
        ({"session_id": "s1", "message_id": "boom"}, 500),
        ({"session_id": "s1", "message_index": -1}, 400),
    ],
)
def test_delete_message_contract_error_status_mapping(payload: dict, expected_status: int):
    fake_chat_service = _FakeChatService()
    client = _build_client(fake_chat_service)

    response = client.request(
        "DELETE",
        "/api/chat/message?context_type=chat",
        json=payload,
    )

    assert response.status_code == expected_status


def test_delete_message_contract_requires_message_selector():
    fake_chat_service = _FakeChatService()
    client = _build_client(fake_chat_service)

    response = client.request(
        "DELETE",
        "/api/chat/message?context_type=chat",
        json={"session_id": "s1"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Either message_id or message_index must be provided"


def test_delete_message_contract_requires_project_id_for_project_context():
    fake_chat_service = _FakeChatService()
    client = _build_client(fake_chat_service)

    response = client.request(
        "DELETE",
        "/api/chat/message",
        json={"session_id": "s1", "message_id": "m1", "context_type": "project"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "project_id is required for project context"
