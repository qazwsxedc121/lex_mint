"""Unit tests for chat application entry service."""

from __future__ import annotations

from typing import Any, cast

import pytest

from src.application.chat.request_contexts import (
    CompareChatRequestContext,
    GroupChatRequestContext,
    SingleChatRequestContext,
)
from src.application.chat.service import ChatApplicationDeps, ChatApplicationService


async def _collect(async_iter):
    items = []
    async for item in async_iter:
        items.append(item)
    return items


class _FakeSingleChatFlowService:
    def __init__(self):
        self.process_message_calls = []
        self.process_message_stream_calls = []

    async def process_message(self, **kwargs):
        self.process_message_calls.append(kwargs)
        return "answer", [{"type": "memory"}]

    async def process_message_stream(self, **kwargs):
        self.process_message_stream_calls.append(kwargs)
        yield "answer"
        yield {"type": "sources", "sources": [{"type": "memory"}]}
        yield {"type": "usage"}


class _FakeCompareFlowService:
    def __init__(self):
        self.calls = []

    async def process_compare_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield {"type": "model_start"}
        yield {"type": "compare_complete"}


class _FakeGroupChatService:
    def __init__(self):
        self.calls = []

    async def process_group_message_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield {"type": "group_start"}
        yield {"type": "group_done"}


class _FakeSessionCommandService:
    def __init__(self):
        self.truncate_calls = []
        self.delete_calls = []
        self.update_calls = []
        self.separator_calls = []
        self.clear_calls = []
        self.compress_calls = []

    async def truncate_messages_after(self, **kwargs):
        self.truncate_calls.append(kwargs)

    async def delete_message(self, **kwargs):
        self.delete_calls.append(kwargs)

    async def update_message_content(self, **kwargs):
        self.update_calls.append(kwargs)

    async def append_separator(self, **kwargs):
        self.separator_calls.append(kwargs)
        return "sep-1"

    async def clear_all_messages(self, **kwargs):
        self.clear_calls.append(kwargs)

    async def compress_context_stream(self, **kwargs):
        self.compress_calls.append(kwargs)
        yield "summary"
        yield {"type": "compression_complete", "message_id": "mid-1", "compressed_count": 2}


class _FakeStorage:
    def __init__(self, session_payload):
        self._session_payload = session_payload
        self.calls = []

    async def get_session(self, session_id, *, context_type="chat", project_id=None):
        self.calls.append(
            {
                "session_id": session_id,
                "context_type": context_type,
                "project_id": project_id,
            }
        )
        return dict(self._session_payload)


async def test_chat_application_service_delegates_single_message():
    single = _FakeSingleChatFlowService()
    service = ChatApplicationService(
        ChatApplicationDeps(
            storage=_FakeStorage({}),
            single_chat_flow_service=single,
            compare_flow_service=_FakeCompareFlowService(),
            group_chat_service=_FakeGroupChatService(),
        )
    )

    response, sources = await service.process_message(
        session_id="s1",
        user_message="hello",
        context_type="chat",
        project_id=None,
    )

    assert response == "answer"
    assert sources == [{"type": "memory"}]
    assert single.process_message_calls == []
    assert len(single.process_message_stream_calls) == 1
    request = single.process_message_stream_calls[0]["request"]
    assert isinstance(request, SingleChatRequestContext)
    assert request.scope.session_id == "s1"


async def test_chat_application_service_delegates_compare_stream():
    compare = _FakeCompareFlowService()
    service = ChatApplicationService(
        ChatApplicationDeps(
            storage=_FakeStorage({}),
            single_chat_flow_service=_FakeSingleChatFlowService(),
            compare_flow_service=compare,
            group_chat_service=_FakeGroupChatService(),
        )
    )

    events = await _collect(
        service.process_compare_stream(
            session_id="s1",
            user_message="hello",
            model_ids=["p:m1", "p:m2"],
        )
    )

    assert events == [{"type": "model_start"}, {"type": "compare_complete"}]
    assert len(compare.calls) == 1
    request = compare.calls[0]["request"]
    assert isinstance(request, CompareChatRequestContext)
    assert request.model_ids == ["p:m1", "p:m2"]


async def test_chat_application_service_auto_stream_routes_to_group_mode():
    group = _FakeGroupChatService()
    storage = _FakeStorage(
        {
            "group_assistants": ["a1", "a2"],
            "group_mode": "committee",
            "group_settings": {"max_rounds": 2},
        }
    )
    service = ChatApplicationService(
        ChatApplicationDeps(
            storage=storage,
            single_chat_flow_service=_FakeSingleChatFlowService(),
            compare_flow_service=_FakeCompareFlowService(),
            group_chat_service=group,
        )
    )

    events = await _collect(service.process_chat_stream(session_id="s1", user_message="hello"))

    assert events == [{"type": "group_start"}, {"type": "group_done"}]
    assert len(group.calls) == 1
    request = group.calls[0]["request"]
    assert isinstance(request, GroupChatRequestContext)
    assert request.group_mode == "committee"
    assert request.group_assistants == ["a1", "a2"]
    assert storage.calls == [{"session_id": "s1", "context_type": "chat", "project_id": None}]


async def test_chat_application_service_auto_stream_routes_to_single_mode():
    single = _FakeSingleChatFlowService()
    storage = _FakeStorage({})
    service = ChatApplicationService(
        ChatApplicationDeps(
            storage=storage,
            single_chat_flow_service=single,
            compare_flow_service=_FakeCompareFlowService(),
            group_chat_service=_FakeGroupChatService(),
        )
    )

    events = await _collect(service.process_chat_stream(session_id="s1", user_message="hello"))

    assert events == [
        "answer",
        {"type": "sources", "sources": [{"type": "memory"}]},
        {"type": "usage"},
    ]
    assert len(single.process_message_stream_calls) == 1


async def test_chat_application_service_passes_temporary_turn_to_single_request():
    single = _FakeSingleChatFlowService()
    storage = _FakeStorage({})
    service = ChatApplicationService(
        ChatApplicationDeps(
            storage=storage,
            single_chat_flow_service=single,
            compare_flow_service=_FakeCompareFlowService(),
            group_chat_service=_FakeGroupChatService(),
        )
    )

    _ = await _collect(
        service.process_chat_stream(
            session_id="s1",
            user_message="hello",
            temporary_turn=True,
        )
    )

    request = single.process_message_stream_calls[0]["request"]
    assert isinstance(request, SingleChatRequestContext)
    assert request.stream.temporary_turn is True
    assert request.stream.skip_user_append is False


async def test_chat_application_service_rejects_temporary_turn_for_group_chat():
    storage = _FakeStorage(
        {
            "group_assistants": ["a1", "a2"],
            "group_mode": "committee",
            "group_settings": {"max_rounds": 2},
        }
    )
    service = ChatApplicationService(
        ChatApplicationDeps(
            storage=storage,
            single_chat_flow_service=_FakeSingleChatFlowService(),
            compare_flow_service=_FakeCompareFlowService(),
            group_chat_service=_FakeGroupChatService(),
        )
    )

    with pytest.raises(ValueError, match="temporary_turn"):
        _ = await _collect(
            service.process_chat_stream(
                session_id="s1",
                user_message="hello",
                temporary_turn=True,
            )
        )


async def test_chat_application_service_delegates_session_commands():
    commands = _FakeSessionCommandService()
    service = ChatApplicationService(
        ChatApplicationDeps(
            storage=_FakeStorage({}),
            single_chat_flow_service=_FakeSingleChatFlowService(),
            compare_flow_service=_FakeCompareFlowService(),
            group_chat_service=_FakeGroupChatService(),
            session_command_service=cast(Any, commands),
        )
    )

    await service.truncate_messages_after(session_id="s1", keep_until_index=3)
    await service.delete_message(session_id="s1", message_id="m1")
    await service.update_message_content(session_id="s1", message_id="m2", content="updated")
    message_id = await service.append_separator(session_id="s1")
    await service.clear_all_messages(session_id="s1")
    events = await _collect(service.compress_context_stream(session_id="s1"))

    assert commands.truncate_calls == [
        {"session_id": "s1", "keep_until_index": 3, "context_type": "chat", "project_id": None}
    ]
    assert commands.delete_calls == [
        {
            "session_id": "s1",
            "message_index": None,
            "message_id": "m1",
            "context_type": "chat",
            "project_id": None,
        }
    ]
    assert commands.update_calls == [
        {
            "session_id": "s1",
            "message_id": "m2",
            "content": "updated",
            "context_type": "chat",
            "project_id": None,
        }
    ]
    assert commands.separator_calls == [
        {"session_id": "s1", "context_type": "chat", "project_id": None}
    ]
    assert commands.clear_calls == [
        {"session_id": "s1", "context_type": "chat", "project_id": None}
    ]
    assert commands.compress_calls == [
        {"session_id": "s1", "context_type": "chat", "project_id": None}
    ]
    assert message_id == "sep-1"
    assert events == [
        "summary",
        {"type": "compression_complete", "message_id": "mid-1", "compressed_count": 2},
    ]
