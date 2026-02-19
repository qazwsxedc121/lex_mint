"""Unit tests for committee mode orchestration in AgentService."""

from types import SimpleNamespace

import pytest

import src.api.services.agent_service_simple as agent_service_module
from src.api.services.agent_service_simple import AgentService


def _build_assistant(name: str, model_id: str, max_rounds: int = 3):
    return SimpleNamespace(
        name=name,
        icon=f"{name.lower()}.png",
        model_id=model_id,
        system_prompt=f"You are {name}.",
        temperature=0.2,
        max_tokens=1024,
        top_p=1.0,
        top_k=40,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        max_rounds=max_rounds,
    )


async def _collect_events(async_iter):
    events = []
    async for event in async_iter:
        events.append(event)
    return events


def test_committee_round_policy_requires_depth_for_multi_member():
    policy = AgentService._resolve_committee_round_policy(3, participant_count=4)
    assert policy["min_member_turns_before_finish"] == 2
    assert policy["min_total_rounds_before_finish"] == 6
    assert policy["max_rounds"] >= 6


@pytest.mark.asyncio
async def test_committee_groupchat_speak_then_finish(monkeypatch):
    """Supervisor can schedule a speaker and then finish with summary synthesis."""
    service = AgentService.__new__(AgentService)

    supervisor_outputs = iter(
        [
            (
                '{"action":"speak","assistant_id":"a2",'
                '"instruction":"Focus on backend risks.","reason":"need specialist"}'
            ),
            (
                '{"action":"finish","reason":"discussion_complete",'
                '"final_response":"Use two-phase rollout."}'
            ),
        ]
    )

    def fake_call_llm(_messages, **_kwargs):
        return next(supervisor_outputs)

    monkeypatch.setattr(agent_service_module, "call_llm", fake_call_llm)

    turn_calls = []

    async def fake_stream_group_assistant_turn(**kwargs):
        turn_calls.append(kwargs)
        assistant_id = kwargs["assistant_id"]
        message_id = f"{assistant_id}-m-{len(turn_calls)}"
        yield {"type": "assistant_start", "assistant_id": assistant_id}
        yield {
            "type": "assistant_message_id",
            "assistant_id": assistant_id,
            "message_id": message_id,
        }
        yield {"type": "assistant_done", "assistant_id": assistant_id}

    async def fake_get_message_content_by_id(**kwargs):
        return f"preview for {kwargs['message_id']}"

    monkeypatch.setattr(service, "_stream_group_assistant_turn", fake_stream_group_assistant_turn)
    monkeypatch.setattr(service, "_get_message_content_by_id", fake_get_message_content_by_id)

    assistant_config_map = {
        "a1": _build_assistant("Supervisor", "deepseek:chat", max_rounds=3),
        "a2": _build_assistant("Architect", "deepseek:chat", max_rounds=3),
    }
    assistant_name_map = {"a1": "Supervisor", "a2": "Architect"}

    events = await _collect_events(
        service._process_committee_group_message_stream(
            session_id="s1",
            raw_user_message="How should we implement committee mode?",
            group_assistants=["a1", "a2"],
            assistant_name_map=assistant_name_map,
            assistant_config_map=assistant_config_map,
            reasoning_effort=None,
            context_type="chat",
            project_id=None,
            search_context=None,
            search_sources=[],
        )
    )

    round_events = [e for e in events if e.get("type") == "group_round_start"]
    assert [e["round"] for e in round_events] == [1, 2]

    action_events = [e for e in events if e.get("type") == "group_action"]
    assert action_events[0]["action"] == "speak"
    assert action_events[0]["assistant_id"] == "a2"
    assert action_events[0]["reason"] == "need specialist"
    assert action_events[1]["action"] == "finish"
    assert action_events[1]["reason"] == "discussion_complete"

    assert len(turn_calls) == 2
    assert turn_calls[0]["assistant_id"] == "a2"
    assert turn_calls[0]["instruction"] == "Focus on backend risks."
    assert turn_calls[1]["assistant_id"] == "a1"
    assert "Committee orchestration is ending (reason: discussion_complete)." in turn_calls[1][
        "instruction"
    ]

    assert events[-1] == {
        "type": "group_done",
        "mode": "committee",
        "reason": "discussion_complete",
        "rounds": 1,
    }


@pytest.mark.asyncio
async def test_committee_groupchat_invalid_supervisor_output_uses_fallback(monkeypatch):
    """Invalid supervisor JSON falls back to a valid speaker and forced summary finish."""
    service = AgentService.__new__(AgentService)

    def fake_call_llm(_messages, **_kwargs):
        return "this is not valid json"

    monkeypatch.setattr(agent_service_module, "call_llm", fake_call_llm)

    turn_calls = []

    async def fake_stream_group_assistant_turn(**kwargs):
        turn_calls.append(kwargs)
        assistant_id = kwargs["assistant_id"]
        message_id = f"{assistant_id}-m-{len(turn_calls)}"
        yield {"type": "assistant_start", "assistant_id": assistant_id}
        yield {
            "type": "assistant_message_id",
            "assistant_id": assistant_id,
            "message_id": message_id,
        }
        yield {"type": "assistant_done", "assistant_id": assistant_id}

    async def fake_get_message_content_by_id(**_kwargs):
        return "fallback content preview"

    monkeypatch.setattr(service, "_stream_group_assistant_turn", fake_stream_group_assistant_turn)
    monkeypatch.setattr(service, "_get_message_content_by_id", fake_get_message_content_by_id)

    assistant_config_map = {
        "a1": _build_assistant("Supervisor", "deepseek:chat", max_rounds=1),
        "a2": _build_assistant("Implementer", "deepseek:chat", max_rounds=1),
    }
    assistant_name_map = {"a1": "Supervisor", "a2": "Implementer"}

    events = await _collect_events(
        service._process_committee_group_message_stream(
            session_id="s2",
            raw_user_message="Need a rollout plan.",
            group_assistants=["a1", "a2"],
            assistant_name_map=assistant_name_map,
            assistant_config_map=assistant_config_map,
            reasoning_effort=None,
            context_type="chat",
            project_id=None,
            search_context=None,
            search_sources=[],
        )
    )

    action_event = next(e for e in events if e.get("type") == "group_action")
    assert action_event["action"] == "speak"
    assert action_event["assistant_id"] == "a2"
    assert action_event["reason"] == "invalid_supervisor_output"
    assert "Please contribute your best analysis as Implementer." == action_event["instruction"]

    assert len(turn_calls) == 2
    assert turn_calls[0]["assistant_id"] == "a2"
    assert turn_calls[1]["assistant_id"] == "a1"
    assert "Committee orchestration is ending (reason: max_rounds_reached)." in turn_calls[1][
        "instruction"
    ]

    assert events[-1]["type"] == "group_done"
    assert events[-1]["reason"] == "max_rounds_reached"
    assert events[-1]["rounds"] == 1


@pytest.mark.asyncio
async def test_committee_groupchat_no_valid_participants():
    service = AgentService.__new__(AgentService)

    events = await _collect_events(
        service._process_committee_group_message_stream(
            session_id="s3",
            raw_user_message="Hello",
            group_assistants=["ghost-assistant"],
            assistant_name_map={},
            assistant_config_map={},
            reasoning_effort=None,
            context_type="chat",
            project_id=None,
            search_context=None,
            search_sources=[],
        )
    )

    assert events == [
        {
            "type": "group_done",
            "mode": "committee",
            "reason": "no_valid_participants",
            "rounds": 0,
        }
    ]


@pytest.mark.asyncio
async def test_committee_groupchat_role_drift_retries_once(monkeypatch):
    service = AgentService.__new__(AgentService)

    supervisor_outputs = iter(
        [
            '{"action":"speak","assistant_id":"a2","instruction":"Provide implementation details.","reason":"need specialist"}',
            '{"action":"finish","reason":"discussion_complete"}',
        ]
    )

    def fake_call_llm(_messages, **_kwargs):
        return next(supervisor_outputs)

    monkeypatch.setattr(agent_service_module, "call_llm", fake_call_llm)

    turn_calls = []

    async def fake_stream_group_assistant_turn(**kwargs):
        turn_calls.append(kwargs)
        assistant_id = kwargs["assistant_id"]
        message_id = f"{assistant_id}-m-{len(turn_calls)}"
        yield {"type": "assistant_start", "assistant_id": assistant_id}
        yield {
            "type": "assistant_message_id",
            "assistant_id": assistant_id,
            "message_id": message_id,
        }
        yield {"type": "assistant_done", "assistant_id": assistant_id}

    async def fake_get_message_content_by_id(**kwargs):
        message_id = kwargs.get("message_id") or ""
        if message_id.endswith("-1"):
            return "[As Supervisor] Here is my review."
        return "Implementation specialist response."

    monkeypatch.setattr(service, "_stream_group_assistant_turn", fake_stream_group_assistant_turn)
    monkeypatch.setattr(service, "_get_message_content_by_id", fake_get_message_content_by_id)

    assistant_config_map = {
        "a1": _build_assistant("Supervisor", "deepseek:chat", max_rounds=3),
        "a2": _build_assistant("Implementer", "deepseek:chat", max_rounds=3),
    }
    assistant_name_map = {"a1": "Supervisor", "a2": "Implementer"}

    events = await _collect_events(
        service._process_committee_group_message_stream(
            session_id="s4",
            raw_user_message="Need committee implementation advice.",
            group_assistants=["a1", "a2"],
            assistant_name_map=assistant_name_map,
            assistant_config_map=assistant_config_map,
            reasoning_effort=None,
            context_type="chat",
            project_id=None,
            search_context=None,
            search_sources=[],
        )
    )

    retry_events = [e for e in events if e.get("type") == "group_action" and e.get("action") == "role_retry"]
    assert len(retry_events) == 1
    assert retry_events[0]["assistant_id"] == "a2"
    assert retry_events[0]["reason"] == "role_drift_claimed_a1"

    assert len(turn_calls) == 3
    assert turn_calls[0]["assistant_id"] == "a2"
    assert turn_calls[1]["assistant_id"] == "a2"
    assert "Role correction required:" in (turn_calls[1].get("instruction") or "")
    assert turn_calls[2]["assistant_id"] == "a1"

    assert events[-1]["type"] == "group_done"
    assert events[-1]["reason"] == "discussion_complete"
