"""Unit tests for the unified chat orchestration gateway."""

from __future__ import annotations

from src.application.chat.orchestration_gateway import (
    ChatOrchestrationGateway,
    ChatOrchestrationGatewayDeps,
)
from src.application.chat.request_contexts import (
    CompareChatRequestContext,
    ConversationScope,
    GroupChatRequestContext,
    SingleChatRequestContext,
    UserInputPayload,
)


async def _collect(async_iter):
    return [item async for item in async_iter]


class _FakeSingle:
    def __init__(self):
        self.process_message_calls = []
        self.process_message_stream_calls = []

    async def process_message(self, **kwargs):
        self.process_message_calls.append(kwargs)
        return "ok", [{"type": "source"}]

    async def process_message_stream(self, **kwargs):
        self.process_message_stream_calls.append(kwargs)
        yield "ok"
        yield {"type": "sources", "sources": [{"type": "source"}]}


class _FakeGroup:
    async def process_group_message_stream(self, **kwargs):
        request = kwargs.get("request")
        yield {"type": getattr(request, "group_mode", None)}


class _FakeCompare:
    async def process_compare_stream(self, **kwargs):
        yield {"type": "compare"}


async def test_gateway_routes_single_direct_and_group_modes():
    single = _FakeSingle()
    gateway = ChatOrchestrationGateway(
        ChatOrchestrationGatewayDeps(
            single_chat_flow_service=single,
            compare_flow_service=_FakeCompare(),
            group_chat_service=_FakeGroup(),
        )
    )

    message, sources = await gateway.run_single_message(
        request=SingleChatRequestContext(
            scope=ConversationScope(session_id="s"),
            user_input=UserInputPayload(user_message="u"),
        )
    )
    group_events = await _collect(
        gateway.stream_group(
            request=GroupChatRequestContext(
                scope=ConversationScope(session_id="s"),
                user_input=UserInputPayload(user_message="u"),
                group_assistants=["a"],
                group_mode="committee",
            )
        )
    )

    assert message == "ok"
    assert sources == [{"type": "source"}]
    assert single.process_message_calls == []
    assert len(single.process_message_stream_calls) == 1
    assert group_events == [{"type": "committee"}]


async def test_gateway_routes_compare_stream():
    gateway = ChatOrchestrationGateway(
        ChatOrchestrationGatewayDeps(
            single_chat_flow_service=_FakeSingle(),
            compare_flow_service=_FakeCompare(),
            group_chat_service=_FakeGroup(),
        )
    )

    compare_events = await _collect(
        gateway.stream_compare(
            request=CompareChatRequestContext(
                scope=ConversationScope(session_id="s"),
                user_input=UserInputPayload(user_message="u"),
                model_ids=["m1", "m2"],
            )
        )
    )

    assert compare_events == [{"type": "compare"}]
