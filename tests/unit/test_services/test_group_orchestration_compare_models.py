"""Unit tests for compare-models orchestrator contract."""

import pytest

from src.api.services.group_orchestration import (
    CompareModelsOrchestrator,
    CompareModelsSettings,
    OrchestrationRequest,
)
from src.providers.types import CostInfo, TokenUsage


async def _collect_events(async_iter):
    events = []
    async for event in async_iter:
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_compare_models_streams_multiplexed_events_and_completion():
    usage = TokenUsage(prompt_tokens=5, completion_tokens=7, total_tokens=12)
    cost = CostInfo(input_cost=0.01, output_cost=0.02, total_cost=0.03, currency="USD")

    async def fake_call_llm_stream(_messages, **kwargs):
        model_id = kwargs["model_id"]
        yield f"{model_id}-chunk1"
        yield {"type": "usage", "usage": usage}
        yield f"{model_id}-chunk2"

    class FakePricingService:
        @staticmethod
        def calculate_cost(_provider_id, _model_id, _usage):
            return cost

    orchestrator = CompareModelsOrchestrator(
        call_llm_stream=fake_call_llm_stream,
        pricing_service=FakePricingService(),
        file_service=object(),
        resolve_model_name=lambda model_id: f"name-{model_id}",
    )
    request = OrchestrationRequest(
        session_id="s1",
        mode="compare_models",
        user_message="hello",
        participants=["m1", "m2"],
        assistant_name_map={},
        assistant_config_map={},
        settings=CompareModelsSettings(
            messages=[{"role": "user", "content": "hello"}],
            model_ids=["m1", "m2"],
            system_prompt=None,
            max_rounds=3,
        ),
    )

    events = await _collect_events(orchestrator.stream(request))
    assert any(event.get("type") == "model_start" and event.get("model_id") == "m1" for event in events)
    assert any(event.get("type") == "model_start" and event.get("model_id") == "m2" for event in events)
    assert any(event.get("type") == "model_done" and event.get("model_id") == "m1" for event in events)
    assert any(event.get("type") == "model_done" and event.get("model_id") == "m2" for event in events)

    completion = events[-1]
    assert completion["type"] == "compare_complete"
    assert set(completion["model_results"].keys()) == {"m1", "m2"}
    assert completion["model_results"]["m1"]["model_name"] == "name-m1"


@pytest.mark.asyncio
async def test_compare_models_rejects_mismatched_mode():
    async def fake_call_llm_stream(*_args, **_kwargs):
        if False:
            yield ""

    class FakePricingService:
        @staticmethod
        def calculate_cost(_provider_id, _model_id, _usage):
            return None

    orchestrator = CompareModelsOrchestrator(
        call_llm_stream=fake_call_llm_stream,
        pricing_service=FakePricingService(),
        file_service=object(),
    )
    request = OrchestrationRequest(
        session_id="s2",
        mode="single_turn",
        user_message="hello",
        participants=[],
        assistant_name_map={},
        assistant_config_map={},
        settings=CompareModelsSettings(
            messages=[],
            model_ids=["m1", "m2"],
            system_prompt=None,
            max_rounds=None,
        ),
    )

    with pytest.raises(ValueError, match="mode=compare_models"):
        await _collect_events(orchestrator.stream(request))
