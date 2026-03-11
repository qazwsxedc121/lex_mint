"""Unit tests for committee orchestration behavior."""

from dataclasses import dataclass
from typing import List, Optional

import pytest

from src.application.chat.group_orchestration_support_service import GroupOrchestrationSupportService
from src.application.chat.orchestration import (
    CommitteeOrchestrator,
    CommitteePolicy,
    OrchestrationRequest,
    ResolvedCommitteeSettings,
)
from src.application.chat.service_contracts import AssistantLike


@dataclass
class _AssistantStub:
    id: str
    name: str
    model_id: str
    icon: str
    system_prompt: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    top_p: Optional[float]
    top_k: Optional[int]
    frequency_penalty: Optional[float]
    presence_penalty: Optional[float]
    max_rounds: Optional[int]
    memory_enabled: bool = True
    knowledge_base_ids: Optional[List[str]] = None
    enabled: bool = True


def _build_assistant(name: str, model_id: str, max_rounds: int = 3) -> AssistantLike:
    return _AssistantStub(
        id=name.lower(),
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


def _build_orchestrator(*, llm_call, stream_group_assistant_turn, get_message_content_by_id):
    support = GroupOrchestrationSupportService(
        storage=object(),
        pricing_service=object(),
        memory_service=object(),
        file_service=object(),
        build_rag_context_and_sources=None,
        truncate_log_text=lambda text, _limit: text or "",
        build_messages_preview_for_log=lambda messages: messages,
        log_group_trace=lambda *_args, **_kwargs: None,
    )
    return CommitteeOrchestrator(
        llm_call=llm_call,
        assistant_params_from_config=support.assistant_params_from_config,
        stream_group_assistant_turn=stream_group_assistant_turn,
        get_message_content_by_id=get_message_content_by_id,
        build_structured_turn_summary=support.build_structured_turn_summary,
        build_committee_turn_packet=support.build_committee_turn_packet,
        detect_group_role_drift=support.detect_group_role_drift,
        build_role_retry_instruction=support.build_role_retry_instruction,
        truncate_log_text=lambda text, _limit: text or "",
        log_group_trace=lambda *_args, **_kwargs: None,
    )


def _build_request(
    *,
    raw_user_message: str,
    group_assistants: List[str],
    assistant_name_map,
    assistant_config_map,
    settings: Optional[ResolvedCommitteeSettings] = None,
):
    return OrchestrationRequest(
        session_id="s1",
        mode="committee",
        user_message=raw_user_message,
        participants=group_assistants,
        assistant_name_map=assistant_name_map,
        assistant_config_map=assistant_config_map,
        settings=settings
        or ResolvedCommitteeSettings(
            supervisor_id=group_assistants[0] if group_assistants else "a1",
            max_rounds=2,
            min_member_turns_before_finish=1,
            min_total_rounds_before_finish=1 if len(group_assistants) > 1 else 0,
            max_parallel_speakers=3,
            role_retry_limit=1,
        ),
        context_type="chat",
        project_id=None,
        search_context=None,
        search_sources=[],
    )


def test_committee_round_policy_requires_depth_for_multi_member():
    policy = CommitteePolicy.resolve_committee_round_policy(3, participant_count=4)
    assert policy["min_member_turns_before_finish"] == 2
    assert policy["min_total_rounds_before_finish"] == 6
    assert policy["max_rounds"] >= 6


@pytest.mark.asyncio
async def test_committee_orchestrator_speak_then_finish():
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

    turn_calls = []

    async def fake_stream_group_assistant_turn(**kwargs):
        turn_calls.append(kwargs)
        assistant_id = kwargs["assistant_id"]
        message_id = f"{assistant_id}-m-{len(turn_calls)}"
        yield {"type": "assistant_start", "assistant_id": assistant_id}
        yield {"type": "assistant_message_id", "assistant_id": assistant_id, "message_id": message_id}
        yield {"type": "assistant_done", "assistant_id": assistant_id}

    async def fake_get_message_content_by_id(**kwargs):
        return f"preview for {kwargs['message_id']}"

    assistant_config_map = {
        "a1": _build_assistant("Supervisor", "deepseek:chat", max_rounds=3),
        "a2": _build_assistant("Architect", "deepseek:chat", max_rounds=3),
    }
    assistant_name_map = {"a1": "Supervisor", "a2": "Architect"}
    orchestrator = _build_orchestrator(
        llm_call=fake_call_llm,
        stream_group_assistant_turn=fake_stream_group_assistant_turn,
        get_message_content_by_id=fake_get_message_content_by_id,
    )

    events = await _collect_events(
        orchestrator.stream(
            _build_request(
                raw_user_message="How should we implement committee mode?",
                group_assistants=["a1", "a2"],
                assistant_name_map=assistant_name_map,
                assistant_config_map=assistant_config_map,
            )
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
    assert "Committee orchestration is ending (reason: discussion_complete)." in turn_calls[1]["instruction"]

    assert events[-1] == {
        "type": "group_done",
        "mode": "committee",
        "reason": "discussion_complete",
        "rounds": 1,
    }


@pytest.mark.asyncio
async def test_committee_orchestrator_invalid_supervisor_output_uses_fallback():
    def fake_call_llm(_messages, **_kwargs):
        return "this is not valid json"

    turn_calls = []

    async def fake_stream_group_assistant_turn(**kwargs):
        turn_calls.append(kwargs)
        assistant_id = kwargs["assistant_id"]
        message_id = f"{assistant_id}-m-{len(turn_calls)}"
        yield {"type": "assistant_start", "assistant_id": assistant_id}
        yield {"type": "assistant_message_id", "assistant_id": assistant_id, "message_id": message_id}
        yield {"type": "assistant_done", "assistant_id": assistant_id}

    async def fake_get_message_content_by_id(**_kwargs):
        return "fallback content preview"

    assistant_config_map = {
        "a1": _build_assistant("Supervisor", "deepseek:chat", max_rounds=1),
        "a2": _build_assistant("Implementer", "deepseek:chat", max_rounds=1),
    }
    assistant_name_map = {"a1": "Supervisor", "a2": "Implementer"}
    orchestrator = _build_orchestrator(
        llm_call=fake_call_llm,
        stream_group_assistant_turn=fake_stream_group_assistant_turn,
        get_message_content_by_id=fake_get_message_content_by_id,
    )

    events = await _collect_events(
        orchestrator.stream(
            _build_request(
                raw_user_message="Need a rollout plan.",
                group_assistants=["a1", "a2"],
                assistant_name_map=assistant_name_map,
                assistant_config_map=assistant_config_map,
                settings=ResolvedCommitteeSettings(
                    supervisor_id="a1",
                    max_rounds=1,
                    min_member_turns_before_finish=1,
                    min_total_rounds_before_finish=1,
                    max_parallel_speakers=3,
                    role_retry_limit=1,
                ),
            )
        )
    )

    action_event = next(e for e in events if e.get("type") == "group_action")
    assert action_event["action"] == "speak"
    assert action_event["assistant_id"] == "a2"
    assert action_event["reason"] == "invalid_supervisor_output"
    assert action_event["instruction"] == "Please contribute your best analysis as Implementer."

    assert len(turn_calls) == 2
    assert turn_calls[0]["assistant_id"] == "a2"
    assert turn_calls[1]["assistant_id"] == "a1"
    assert "Committee orchestration is ending (reason: max_rounds_reached)." in turn_calls[1]["instruction"]

    assert events[-1]["type"] == "group_done"
    assert events[-1]["reason"] == "max_rounds_reached"
    assert events[-1]["rounds"] == 1


@pytest.mark.asyncio
async def test_committee_orchestrator_no_valid_participants():
    async def fake_stream_group_assistant_turn(**_kwargs):
        if False:
            yield {}

    async def fake_get_message_content_by_id(**_kwargs):
        return ""

    orchestrator = _build_orchestrator(
        llm_call=lambda *_args, **_kwargs: "",
        stream_group_assistant_turn=fake_stream_group_assistant_turn,
        get_message_content_by_id=fake_get_message_content_by_id,
    )

    events = await _collect_events(
        orchestrator.stream(
            _build_request(
                raw_user_message="Hello",
                group_assistants=["ghost-assistant"],
                assistant_name_map={},
                assistant_config_map={},
                settings=ResolvedCommitteeSettings(
                    supervisor_id="ghost-assistant",
                    max_rounds=1,
                    min_member_turns_before_finish=1,
                    min_total_rounds_before_finish=0,
                    max_parallel_speakers=3,
                    role_retry_limit=1,
                ),
            )
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
async def test_committee_orchestrator_role_drift_retries_once():
    supervisor_outputs = iter(
        [
            '{"action":"speak","assistant_id":"a2","instruction":"Provide implementation details.","reason":"need specialist"}',
            '{"action":"finish","reason":"discussion_complete"}',
        ]
    )

    def fake_call_llm(_messages, **_kwargs):
        return next(supervisor_outputs)

    turn_calls = []

    async def fake_stream_group_assistant_turn(**kwargs):
        turn_calls.append(kwargs)
        assistant_id = kwargs["assistant_id"]
        message_id = f"{assistant_id}-m-{len(turn_calls)}"
        yield {"type": "assistant_start", "assistant_id": assistant_id}
        yield {"type": "assistant_message_id", "assistant_id": assistant_id, "message_id": message_id}
        yield {"type": "assistant_done", "assistant_id": assistant_id}

    async def fake_get_message_content_by_id(**kwargs):
        message_id = kwargs.get("message_id") or ""
        if message_id.endswith("-1"):
            return "[As Supervisor] Here is my review."
        return "Implementation specialist response."

    assistant_config_map = {
        "a1": _build_assistant("Supervisor", "deepseek:chat", max_rounds=3),
        "a2": _build_assistant("Implementer", "deepseek:chat", max_rounds=3),
    }
    assistant_name_map = {"a1": "Supervisor", "a2": "Implementer"}
    orchestrator = _build_orchestrator(
        llm_call=fake_call_llm,
        stream_group_assistant_turn=fake_stream_group_assistant_turn,
        get_message_content_by_id=fake_get_message_content_by_id,
    )

    events = await _collect_events(
        orchestrator.stream(
            _build_request(
                raw_user_message="Need committee implementation advice.",
                group_assistants=["a1", "a2"],
                assistant_name_map=assistant_name_map,
                assistant_config_map=assistant_config_map,
            )
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


@pytest.mark.asyncio
async def test_committee_orchestrator_parallel_speak_then_finish():
    supervisor_outputs = iter(
        [
            (
                '{"action":"parallel_speak","assistant_ids":["a2","a3"],'
                '"instruction":"Contribute from your specialty and challenge assumptions.",'
                '"reason":"accelerate_coverage"}'
            ),
            '{"action":"finish","reason":"discussion_complete"}',
        ]
    )

    def fake_call_llm(_messages, **_kwargs):
        return next(supervisor_outputs)

    turn_calls = []
    call_index = {"value": 0}

    async def fake_stream_group_assistant_turn(**kwargs):
        turn_calls.append(kwargs)
        call_index["value"] += 1
        idx = call_index["value"]
        assistant_id = kwargs["assistant_id"]
        message_id = f"{assistant_id}-m-{idx}"
        yield {"type": "assistant_start", "assistant_id": assistant_id, "assistant_turn_id": f"t-{idx}"}
        yield {
            "type": "assistant_message_id",
            "assistant_id": assistant_id,
            "assistant_turn_id": f"t-{idx}",
            "message_id": message_id,
        }
        yield {"type": "assistant_done", "assistant_id": assistant_id, "assistant_turn_id": f"t-{idx}"}

    async def fake_get_message_content_by_id(**kwargs):
        return f"parallel content for {kwargs['message_id']}"

    assistant_config_map = {
        "a1": _build_assistant("Supervisor", "deepseek:chat", max_rounds=4),
        "a2": _build_assistant("Architect", "deepseek:chat", max_rounds=4),
        "a3": _build_assistant("Risk", "deepseek:chat", max_rounds=4),
    }
    assistant_name_map = {"a1": "Supervisor", "a2": "Architect", "a3": "Risk"}
    orchestrator = _build_orchestrator(
        llm_call=fake_call_llm,
        stream_group_assistant_turn=fake_stream_group_assistant_turn,
        get_message_content_by_id=fake_get_message_content_by_id,
    )

    events = await _collect_events(
        orchestrator.stream(
            _build_request(
                raw_user_message="Need plan and risks.",
                group_assistants=["a1", "a2", "a3"],
                assistant_name_map=assistant_name_map,
                assistant_config_map=assistant_config_map,
            )
        )
    )

    round_events = [e for e in events if e.get("type") == "group_round_start"]
    assert [e["round"] for e in round_events] == [1, 2]

    action_events = [e for e in events if e.get("type") == "group_action"]
    assert action_events[0]["action"] == "parallel_speak"
    assert set(action_events[0]["assistant_ids"]) == {"a2", "a3"}
    assert action_events[1]["action"] == "finish"

    assert len(turn_calls) == 3
    assert {turn_calls[0]["assistant_id"], turn_calls[1]["assistant_id"]} == {"a2", "a3"}
    assert turn_calls[2]["assistant_id"] == "a1"

    assert events[-1] == {
        "type": "group_done",
        "mode": "committee",
        "reason": "discussion_complete",
        "rounds": 1,
    }
