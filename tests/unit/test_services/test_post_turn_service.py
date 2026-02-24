"""Unit tests for post-turn persistence and side-effect handling."""

import asyncio
from types import SimpleNamespace

import pytest

from src.api.services.post_turn_service import PostTurnService


class _FakeStorage:
    def __init__(self):
        self.append_calls = []
        self._session = {
            "temporary": False,
            "title": "New Chat",
            "state": {"messages": [{"role": "user"}, {"role": "assistant"}]},
        }

    async def append_message(self, *args, **kwargs):
        self.append_calls.append((args, kwargs))
        return "assistant-msg-1"

    async def get_session(self, *_args, **_kwargs):
        return self._session


class _FakeMemoryService:
    def __init__(self):
        self.calls = []

    async def extract_and_persist_from_turn(self, **kwargs):
        self.calls.append(kwargs)


class _FakeTitleService:
    def __init__(self, **_kwargs):
        self.config = SimpleNamespace(enabled=True, trigger_threshold=2)
        self.generated = []

    def should_generate_title(self, _message_count, _current_title):
        return True

    async def generate_title_async(self, session_id):
        self.generated.append(session_id)


class _FakeFollowupService:
    def __init__(self):
        self.config = SimpleNamespace(enabled=True, count=2)

    async def generate_followups_async(self, _messages):
        return ["Q1", "Q2"]


@pytest.mark.asyncio
async def test_finalize_single_turn_persists_and_schedules_tasks():
    storage = _FakeStorage()
    memory_service = _FakeMemoryService()
    title_service = _FakeTitleService()
    scheduled_tasks = []

    def scheduler(coro):
        task = asyncio.create_task(coro)
        scheduled_tasks.append(task)
        return task

    service = PostTurnService(
        storage=storage,
        memory_service=memory_service,
        task_scheduler=scheduler,
        title_service_factory=lambda **kwargs: title_service,
    )

    message_id = await service.finalize_single_turn(
        session_id="s1",
        assistant_message="answer",
        usage_data=None,
        cost_data=None,
        sources=[{"type": "memory"}],
        raw_user_message="question",
        assistant_id="assistant-1",
        is_legacy_assistant=False,
        assistant_memory_enabled=True,
        user_message_id="user-1",
        context_type="chat",
        project_id=None,
    )
    await asyncio.gather(*scheduled_tasks)

    assert message_id == "assistant-msg-1"
    assert len(storage.append_calls) == 1
    _, append_kwargs = storage.append_calls[0]
    assert append_kwargs["sources"] == [{"type": "memory"}]
    assert len(memory_service.calls) == 1
    assert memory_service.calls[0]["assistant_id"] == "assistant-1"
    assert title_service.generated == ["s1"]


@pytest.mark.asyncio
async def test_generate_followup_questions_uses_followup_service():
    storage = _FakeStorage()
    service = PostTurnService(
        storage=storage,
        memory_service=_FakeMemoryService(),
        followup_service_factory=_FakeFollowupService,
    )

    questions = await service.generate_followup_questions(
        session_id="s2",
        context_type="chat",
        project_id=None,
    )

    assert questions == ["Q1", "Q2"]
