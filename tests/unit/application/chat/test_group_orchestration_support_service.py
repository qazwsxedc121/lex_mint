"""Unit tests for group orchestration support service."""

from types import SimpleNamespace

from src.application.chat.group_orchestration_support_service import (
    GroupOrchestrationSupportService,
)
from src.application.chat.orchestration import CommitteeOrchestrator, RoundRobinOrchestrator


def _build_service() -> GroupOrchestrationSupportService:
    return GroupOrchestrationSupportService(
        storage=SimpleNamespace(),
        pricing_service=SimpleNamespace(),
        memory_service=SimpleNamespace(),
        file_service=SimpleNamespace(),
        build_rag_context_and_sources=None,
        truncate_log_text=lambda text, _limit: text or "",
        build_messages_preview_for_log=lambda messages: messages,
        log_group_trace=lambda *_args, **_kwargs: None,
    )


def test_build_group_identity_prompt_marks_current_participant():
    prompt = GroupOrchestrationSupportService.build_group_identity_prompt(
        current_assistant_id="assistant-2",
        current_assistant_name="Architect",
        group_assistants=["assistant-1", "assistant-2"],
        assistant_name_map={
            "assistant-1": "Supervisor",
            "assistant-2": "Architect",
        },
    )

    assert "You are Architect [assistant-2]" in prompt
    assert "1. Supervisor [assistant-1]" in prompt
    assert "2. Architect [assistant-2] (you)" in prompt


def test_build_group_instruction_prompt_includes_packet_json():
    prompt = GroupOrchestrationSupportService.build_group_instruction_prompt(
        instruction="Focus on trade-offs.",
        structured_packet={"identity": {"assistant_id": "assistant-2"}},
    )

    assert "Committee instruction:" in prompt
    assert "Focus on trade-offs." in prompt
    assert "Committee turn packet (JSON):" in prompt
    assert '"assistant_id": "assistant-2"' in prompt


def test_detect_group_role_drift_flags_other_participant_claim():
    reason = GroupOrchestrationSupportService.detect_group_role_drift(
        content="[Supervisor] I think we should ship this now.",
        expected_assistant_id="assistant-2",
        expected_assistant_name="Architect",
        participant_name_map={
            "assistant-1": "Supervisor",
            "assistant-2": "Architect",
        },
    )

    assert reason == "role_drift_claimed_assistant-1"


def test_create_orchestrators_preserve_runtime_callbacks():
    service = _build_service()

    async def fake_stream_group_assistant_turn(**_kwargs):
        if False:
            yield {}

    async def fake_get_message_content_by_id(**_kwargs):
        return ""

    committee = service.create_committee_orchestrator(
        llm_call=lambda *_args, **_kwargs: "",
        stream_group_assistant_turn=fake_stream_group_assistant_turn,
        get_message_content_by_id=fake_get_message_content_by_id,
    )
    round_robin = service.create_round_robin_orchestrator(
        stream_group_assistant_turn=fake_stream_group_assistant_turn,
    )

    assert isinstance(committee, CommitteeOrchestrator)
    assert committee.stream_group_assistant_turn is fake_stream_group_assistant_turn
    assert committee.get_message_content_by_id is fake_get_message_content_by_id
    assert isinstance(round_robin, RoundRobinOrchestrator)
    assert round_robin.stream_group_assistant_turn is fake_stream_group_assistant_turn
