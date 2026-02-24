"""Unit tests for single-turn orchestrator contract."""

import pytest

from src.api.services.group_orchestration import (
    OrchestrationRequest,
    SingleTurnOrchestrator,
    SingleTurnSettings,
)
from src.providers.types import CostInfo, TokenUsage


async def _collect_events(async_iter):
    events = []
    async for event in async_iter:
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_single_turn_stream_emits_usage_chunks_and_completion():
    usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    cost = CostInfo(input_cost=0.1, output_cost=0.2, total_cost=0.3, currency="USD")

    async def fake_call_llm_stream(*_args, **_kwargs):
        yield {"type": "context_info", "context_budget": 100}
        yield "hello "
        yield {"type": "usage", "usage": usage}
        yield "world"
        yield {"type": "tool_diagnostics", "tool_search_count": 1}

    class FakePricingService:
        @staticmethod
        def calculate_cost(_provider_id, _model_id, _usage):
            return cost

    orchestrator = SingleTurnOrchestrator(
        call_llm_stream=fake_call_llm_stream,
        pricing_service=FakePricingService(),
        file_service=object(),
    )
    request = OrchestrationRequest(
        session_id="s1",
        mode="single_turn",
        user_message="hello",
        participants=[],
        assistant_name_map={},
        assistant_config_map={},
        settings=SingleTurnSettings(
            messages=[{"role": "user", "content": "hello"}],
            model_id="openai:gpt-4o-mini",
            system_prompt=None,
            max_rounds=3,
        ),
    )

    events = await _collect_events(orchestrator.stream(request))
    assert [event["type"] for event in events] == [
        "context_info",
        "assistant_chunk",
        "usage",
        "assistant_chunk",
        "single_turn_complete",
    ]
    complete_event = events[-1]
    content, final_usage, final_cost, tool_diagnostics = SingleTurnOrchestrator.parse_completion_event(
        complete_event
    )
    assert content == "hello world"
    assert final_usage == usage
    assert final_cost == cost
    assert tool_diagnostics == {"type": "tool_diagnostics", "tool_search_count": 1}


@pytest.mark.asyncio
async def test_single_turn_rejects_mismatched_mode():
    async def fake_call_llm_stream(*_args, **_kwargs):
        if False:
            yield ""

    class FakePricingService:
        @staticmethod
        def calculate_cost(_provider_id, _model_id, _usage):
            return None

    orchestrator = SingleTurnOrchestrator(
        call_llm_stream=fake_call_llm_stream,
        pricing_service=FakePricingService(),
        file_service=object(),
    )
    request = OrchestrationRequest(
        session_id="s2",
        mode="committee",
        user_message="hello",
        participants=[],
        assistant_name_map={},
        assistant_config_map={},
        settings=SingleTurnSettings(
            messages=[],
            model_id="openai:gpt-4o-mini",
            system_prompt=None,
            max_rounds=None,
        ),
    )
    with pytest.raises(ValueError, match="mode=single_turn"):
        await _collect_events(orchestrator.stream(request))
