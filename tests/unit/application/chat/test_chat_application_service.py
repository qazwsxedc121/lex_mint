"""Unit tests for chat application entry service."""

from __future__ import annotations

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
        yield "chunk-1"
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


async def test_chat_application_service_delegates_single_message():
    single = _FakeSingleChatFlowService()
    service = ChatApplicationService(
        ChatApplicationDeps(
            storage=object(),
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
    assert len(single.process_message_calls) == 1
    assert single.process_message_calls[0]["session_id"] == "s1"


async def test_chat_application_service_delegates_single_stream():
    single = _FakeSingleChatFlowService()
    service = ChatApplicationService(
        ChatApplicationDeps(
            storage=object(),
            single_chat_flow_service=single,
            compare_flow_service=_FakeCompareFlowService(),
            group_chat_service=_FakeGroupChatService(),
        )
    )

    events = await _collect(
        service.process_message_stream(
            session_id="s1",
            user_message="hello",
        )
    )

    assert events == ["chunk-1", {"type": "usage"}]
    assert len(single.process_message_stream_calls) == 1
    assert single.process_message_stream_calls[0]["user_message"] == "hello"


async def test_chat_application_service_delegates_compare_stream():
    compare = _FakeCompareFlowService()
    service = ChatApplicationService(
        ChatApplicationDeps(
            storage=object(),
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
    assert compare.calls[0]["model_ids"] == ["p:m1", "p:m2"]


async def test_chat_application_service_delegates_group_stream():
    group = _FakeGroupChatService()
    service = ChatApplicationService(
        ChatApplicationDeps(
            storage=object(),
            single_chat_flow_service=_FakeSingleChatFlowService(),
            compare_flow_service=_FakeCompareFlowService(),
            group_chat_service=group,
        )
    )

    events = await _collect(
        service.process_group_message_stream(
            session_id="s1",
            user_message="hello",
            group_assistants=["a1", "a2"],
        )
    )

    assert events == [{"type": "group_start"}, {"type": "group_done"}]
    assert len(group.calls) == 1
    assert group.calls[0]["group_assistants"] == ["a1", "a2"]
