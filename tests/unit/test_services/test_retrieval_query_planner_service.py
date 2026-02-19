"""Unit tests for retrieval query planner service."""

import asyncio
from types import SimpleNamespace

from src.api.services.retrieval_query_planner_service import RetrievalQueryPlannerService


class _FakeLLM:
    def __init__(self, content: str = "", error: Exception | None = None):
        self._content = content
        self._error = error

    async def ainvoke(self, _prompt: str):
        if self._error is not None:
            raise self._error
        return SimpleNamespace(content=self._content)


def test_plan_queries_returns_original_when_disabled():
    service = RetrievalQueryPlannerService()
    result = asyncio.run(
        service.plan_queries(
            query="what is rag",
            runtime_model_id="openrouter:openai/gpt-4o-mini",
            enabled=False,
            max_queries=3,
            timeout_seconds=4,
            model_id="auto",
        )
    )

    assert result.planner_enabled is False
    assert result.planner_applied is False
    assert result.fallback_used is False
    assert result.reason == "disabled"
    assert result.planned_queries == ["what is rag"]


def test_plan_queries_parses_json_and_deduplicates(monkeypatch):
    service = RetrievalQueryPlannerService()
    monkeypatch.setattr(
        service.model_config_service,
        "get_llm_instance",
        lambda **kwargs: _FakeLLM('{"queries":["what is rag","rag retrieval architecture","what is rag"]}'),
    )

    result = asyncio.run(
        service.plan_queries(
            query="what is rag",
            runtime_model_id="openrouter:openai/gpt-4o-mini",
            enabled=True,
            max_queries=3,
            timeout_seconds=4,
            model_id="auto",
        )
    )

    assert result.planner_enabled is True
    assert result.planner_applied is True
    assert result.fallback_used is False
    assert result.reason == "ok"
    assert result.planner_model_id == "openrouter:openai/gpt-4o-mini"
    assert result.planned_queries == ["what is rag", "rag retrieval architecture"]


def test_plan_queries_recovers_json_from_mixed_output(monkeypatch):
    service = RetrievalQueryPlannerService()
    monkeypatch.setattr(
        service.model_config_service,
        "get_llm_instance",
        lambda **kwargs: _FakeLLM(
            'Plan:\n{"queries":["alpha query","beta query"]}\nDone.'
        ),
    )

    result = asyncio.run(
        service.plan_queries(
            query="alpha query",
            runtime_model_id="deepseek:deepseek-chat",
            enabled=True,
            max_queries=3,
            timeout_seconds=4,
            model_id="auto",
        )
    )

    assert result.reason == "ok"
    assert result.planned_queries == ["alpha query", "beta query"]
    assert result.planner_applied is True


def test_plan_queries_falls_back_on_error(monkeypatch):
    service = RetrievalQueryPlannerService()
    monkeypatch.setattr(
        service.model_config_service,
        "get_llm_instance",
        lambda **kwargs: _FakeLLM(error=RuntimeError("planner failed")),
    )

    result = asyncio.run(
        service.plan_queries(
            query="what is rag",
            runtime_model_id="openrouter:openai/gpt-4o-mini",
            enabled=True,
            max_queries=3,
            timeout_seconds=4,
            model_id="auto",
        )
    )

    assert result.planner_enabled is True
    assert result.planner_applied is False
    assert result.fallback_used is True
    assert result.reason == "error"
    assert result.planned_queries == ["what is rag"]
