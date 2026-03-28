"""Tests for group chat execution service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.application.chat.chat_input_service import PreparedUserInput
from src.application.chat.chat_runtime import ResolvedCommitteeSettings, ResolvedGroupSettings
from src.application.chat.group_chat_service import GroupChatDeps, GroupChatService


class _FakeChatInputService:
    async def prepare_user_input(self, **kwargs):
        return PreparedUserInput(
            raw_user_message=kwargs["raw_user_message"],
            full_message_content=kwargs["expanded_user_message"],
            attachment_metadata=[],
            user_message_id="msg-1",
        )


class _FakePostTurnService:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def schedule_title_generation(self, **kwargs):
        self.calls.append(kwargs)


@dataclass
class _SearchSource:
    url: str

    def model_dump(self):
        return {"url": self.url}


class _FakeSearchService:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    async def search(self, query: str):
        if self.fail:
            raise RuntimeError("search failed")
        return [_SearchSource(url=f"https://example.com/{query}")]

    def build_search_context(self, query: str, sources: list[_SearchSource]):
        return f"context:{query}:{len(sources)}"


class _FakeRoundRobinOrchestrator:
    def __init__(self):
        self.requests: list[Any] = []

    async def stream(self, request):
        self.requests.append(request)
        yield {"type": "assistant_chunk", "content": "reply"}
        yield {"type": "group_done", "mode": "round_robin", "rounds": 1}


class _FakeCommitteeOrchestrator:
    def __init__(self):
        self.requests: list[Any] = []

    async def stream(self, request):
        self.requests.append(request)
        yield {"type": "assistant_chunk", "content": "committee"}
        yield {"type": "group_done", "mode": "committee", "rounds": 1}


async def _build_file_context_block(_refs):
    return "[files]"


def _make_service(*, search_fail: bool = False, trace_enabled: bool = False):
    round_robin = _FakeRoundRobinOrchestrator()
    committee = _FakeCommitteeOrchestrator()
    post_turn = _FakePostTurnService()

    async def _build_group_runtime_assistant(token: str):
        if token == "missing":
            return None
        return (token, {"id": token}, token.upper())

    def _resolve_group_settings(**kwargs):
        mode = kwargs["group_mode"]
        assistants = kwargs["group_assistants"]
        committee_settings = None
        if mode == "committee":
            committee_settings = ResolvedCommitteeSettings(
                supervisor_id=assistants[0],
                max_rounds=2,
                min_member_turns_before_finish=1,
                min_total_rounds_before_finish=1,
                max_parallel_speakers=1,
                role_retry_limit=1,
            )
        return ResolvedGroupSettings(
            group_mode=mode,
            group_assistants=assistants,
            group_settings={},
            committee=committee_settings,
        )

    deps = GroupChatDeps(
        chat_input_service=_FakeChatInputService(),
        post_turn_service=post_turn,
        search_service=_FakeSearchService(fail=search_fail),
        build_file_context_block=_build_file_context_block,
        build_group_runtime_assistant=_build_group_runtime_assistant,
        resolve_group_settings=_resolve_group_settings,
        create_committee_orchestrator=lambda: committee,
        create_round_robin_orchestrator=lambda: round_robin,
        is_group_trace_enabled=lambda: trace_enabled,
        log_group_trace=lambda *args, **kwargs: None,
        truncate_log_text=lambda text, limit: (text or "")[:limit],
        group_trace_preview_chars=20,
    )
    return GroupChatService(deps), round_robin, committee, post_turn


@pytest.mark.asyncio
async def test_group_chat_service_round_robin_flow():
    service, round_robin, _, post_turn = _make_service()

    events = [
        event
        async for event in service.process_group_message_stream(
            session_id="session-1234",
            user_message="hello",
            group_assistants=["a", "a", "b"],
            use_web_search=True,
            file_references=[{"project_id": "p1", "path": "src/app.py"}],
        )
    ]

    assert events[0] == {"type": "user_message_id", "message_id": "msg-1"}
    assert events[-1]["type"] == "group_done"
    assert round_robin.requests[0].participants == ["a", "b"]
    assert round_robin.requests[0].search_context == "context:hello:1"
    assert post_turn.calls[0]["session_id"] == "session-1234"


@pytest.mark.asyncio
async def test_group_chat_service_handles_missing_participants_and_search_failures():
    service, round_robin, _, post_turn = _make_service(search_fail=True)

    events = [
        event
        async for event in service.process_group_message_stream(
            session_id="session-1234",
            user_message="hello",
            group_assistants=["missing"],
            use_web_search=True,
        )
    ]

    assert events[-1]["reason"] == "no_valid_participants"
    assert round_robin.requests == []
    assert post_turn.calls == []


@pytest.mark.asyncio
async def test_group_chat_service_committee_flow_and_trace_id():
    service, _, committee, post_turn = _make_service(trace_enabled=True)

    events = [
        event
        async for event in service.process_group_message_stream(
            session_id="session-12345678",
            user_message="hello committee",
            group_assistants=["lead", "peer"],
            group_mode="committee",
        )
    ]

    assert events[-1]["mode"] == "committee"
    assert committee.requests[0].trace_id is not None
    assert committee.requests[0].settings.supervisor_id == "lead"
    assert post_turn.calls[0]["session_id"] == "session-12345678"
