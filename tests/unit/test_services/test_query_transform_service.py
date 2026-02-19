"""Unit tests for query transform guard behavior."""

import asyncio
from types import SimpleNamespace

from src.api.services.query_transform_service import QueryTransformService


class _FakeLLM:
    def __init__(self, content: str):
        self._content = content

    async def ainvoke(self, _prompt: str):
        return SimpleNamespace(content=self._content)


def test_transform_guard_blocks_entity_hallucination(monkeypatch):
    service = QueryTransformService()
    original_query = '领袖夫人刚出场就用讥讽口吻称呼丈夫"仁慈高贵"，对应哪章？'
    rewritten_query = "《红楼梦》中王熙凤出场时用讥讽口吻称呼丈夫贾琏“仁慈高贵”对应哪一回？"

    monkeypatch.setattr(
        service.model_config_service,
        "get_llm_instance",
        lambda **kwargs: _FakeLLM(rewritten_query),
    )

    result = asyncio.run(
        service.transform_query(
            query=original_query,
            enabled=True,
            mode="rewrite",
            configured_model_id="auto",
            runtime_model_id="deepseek:deepseek-chat",
            timeout_seconds=4,
            guard_enabled=True,
            guard_max_new_terms=2,
        )
    )

    assert result.applied is False
    assert result.effective_query == original_query
    assert result.guard_blocked is True
    assert result.guard_reason.startswith("too_many_new_terms:")


def test_transform_guard_blocks_missing_constraint_keyword(monkeypatch):
    service = QueryTransformService()
    original_query = "主角团队最终找到地球并登陆后的见闻在本书哪一章？"
    rewritten_query = "主角团队找到地球并登陆后的见闻出现在哪一章？"

    monkeypatch.setattr(
        service.model_config_service,
        "get_llm_instance",
        lambda **kwargs: _FakeLLM(rewritten_query),
    )

    result = asyncio.run(
        service.transform_query(
            query=original_query,
            enabled=True,
            mode="rewrite",
            configured_model_id="auto",
            runtime_model_id="deepseek:deepseek-chat",
            timeout_seconds=4,
            guard_enabled=True,
            guard_max_new_terms=2,
        )
    )

    assert result.applied is False
    assert result.effective_query == original_query
    assert result.guard_blocked is True
    assert result.guard_reason.startswith("missing_constraint_keyword:")
