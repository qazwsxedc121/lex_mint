"""Unit tests for committee supervisor normalization rules."""

import pytest

from src.api.services.orchestration.supervisor import CommitteeSupervisor
from src.api.services.orchestration.committee_types import CommitteeRuntimeState, CommitteeTurnRecord


@pytest.mark.asyncio
async def test_supervisor_forces_uncovered_member_before_finish():
    supervisor = CommitteeSupervisor(
        supervisor_id="sup",
        supervisor_name="Supervisor",
        participant_order=["sup", "a", "b"],
        participant_names={"sup": "Supervisor", "a": "Architect", "b": "Product"},
        max_rounds=5,
    )
    state = CommitteeRuntimeState(
        user_message="Plan committee mode.",
        participants={"sup": "Supervisor", "a": "Architect", "b": "Product"},
        round_index=1,
        turns=[
            CommitteeTurnRecord(
                assistant_id="a",
                assistant_name="Architect",
                content_preview="Architecture draft",
            )
        ],
    )

    async def fake_llm(_system_prompt: str, _user_prompt: str) -> str:
        return '{"action":"finish","reason":"good_enough"}'

    decision = await supervisor.decide(state, fake_llm)
    assert decision.action == "speak"
    assert decision.assistant_id == "b"
    assert decision.reason == "coverage_required_before_finish"


@pytest.mark.asyncio
async def test_supervisor_blocks_finish_until_discussion_depth_reached():
    supervisor = CommitteeSupervisor(
        supervisor_id="sup",
        supervisor_name="Supervisor",
        participant_order=["sup", "a", "b"],
        participant_names={"sup": "Supervisor", "a": "Architect", "b": "Product"},
        max_rounds=5,
        min_member_turns_before_finish=2,
        min_total_rounds_before_finish=4,
    )
    state = CommitteeRuntimeState(
        user_message="Plan committee mode.",
        participants={"sup": "Supervisor", "a": "Architect", "b": "Product"},
        round_index=2,
        turns=[
            CommitteeTurnRecord(
                assistant_id="a",
                assistant_name="Architect",
                content_preview="Architecture draft",
            ),
            CommitteeTurnRecord(
                assistant_id="b",
                assistant_name="Product",
                content_preview="Product impact",
            ),
        ],
    )

    async def fake_llm(_system_prompt: str, _user_prompt: str) -> str:
        return '{"action":"finish","reason":"looks_done"}'

    decision = await supervisor.decide(state, fake_llm)
    assert decision.action == "speak"
    assert decision.assistant_id == "a"
    assert decision.reason == "discussion_depth_required_before_finish"


@pytest.mark.asyncio
async def test_supervisor_allows_finish_after_depth_complete():
    supervisor = CommitteeSupervisor(
        supervisor_id="sup",
        supervisor_name="Supervisor",
        participant_order=["sup", "a", "b"],
        participant_names={"sup": "Supervisor", "a": "Architect", "b": "Product"},
        max_rounds=6,
        min_member_turns_before_finish=2,
        min_total_rounds_before_finish=4,
    )
    state = CommitteeRuntimeState(
        user_message="Plan committee mode.",
        participants={"sup": "Supervisor", "a": "Architect", "b": "Product"},
        round_index=4,
        turns=[
            CommitteeTurnRecord(
                assistant_id="a",
                assistant_name="Architect",
                content_preview="Architecture draft",
            ),
            CommitteeTurnRecord(
                assistant_id="b",
                assistant_name="Product",
                content_preview="Product impact",
            ),
            CommitteeTurnRecord(
                assistant_id="a",
                assistant_name="Architect",
                content_preview="Risk mitigations",
            ),
            CommitteeTurnRecord(
                assistant_id="b",
                assistant_name="Product",
                content_preview="Rollout trade-offs",
            ),
        ],
    )

    async def fake_llm(_system_prompt: str, _user_prompt: str) -> str:
        return '{"action":"finish","reason":"discussion_complete"}'

    decision = await supervisor.decide(state, fake_llm)
    assert decision.action == "finish"
    assert decision.reason == "discussion_complete"


@pytest.mark.asyncio
async def test_supervisor_normalizes_parallel_targets():
    supervisor = CommitteeSupervisor(
        supervisor_id="sup",
        supervisor_name="Supervisor",
        participant_order=["sup", "a", "b", "c"],
        participant_names={"sup": "Supervisor", "a": "Architect", "b": "Product", "c": "Ops"},
        max_rounds=6,
        min_member_turns_before_finish=1,
        min_total_rounds_before_finish=0,
    )
    state = CommitteeRuntimeState(
        user_message="Plan committee mode.",
        participants={"sup": "Supervisor", "a": "Architect", "b": "Product", "c": "Ops"},
        round_index=0,
        turns=[],
    )

    async def fake_llm(_system_prompt: str, _user_prompt: str) -> str:
        return '{"action":"parallel_speak","assistant_ids":["a","b","sup","ghost"],"reason":"faster"}'

    decision = await supervisor.decide(state, fake_llm)
    assert decision.action == "parallel_speak"
    assert decision.assistant_ids is not None
    assert "a" in decision.assistant_ids
    assert "b" in decision.assistant_ids
    assert "sup" not in decision.assistant_ids


@pytest.mark.asyncio
async def test_supervisor_parallel_fallbacks_to_single_speak():
    supervisor = CommitteeSupervisor(
        supervisor_id="sup",
        supervisor_name="Supervisor",
        participant_order=["sup", "a", "b"],
        participant_names={"sup": "Supervisor", "a": "Architect", "b": "Product"},
        max_rounds=6,
        min_member_turns_before_finish=1,
        min_total_rounds_before_finish=0,
    )
    state = CommitteeRuntimeState(
        user_message="Plan committee mode.",
        participants={"sup": "Supervisor", "a": "Architect", "b": "Product"},
        round_index=2,
        turns=[
            CommitteeTurnRecord(
                assistant_id="a",
                assistant_name="Architect",
                content_preview="Architecture draft",
            ),
            CommitteeTurnRecord(
                assistant_id="b",
                assistant_name="Product",
                content_preview="Product impact",
            ),
        ],
    )

    async def fake_llm(_system_prompt: str, _user_prompt: str) -> str:
        return '{"action":"parallel_speak","assistant_ids":["a"],"reason":"still_parallel"}'

    decision = await supervisor.decide(state, fake_llm)
    assert decision.action == "speak"
    assert decision.assistant_id == "a"

