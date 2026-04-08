"""Tests for tool gate config router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from src.api.routers import tool_gate_config as router


@pytest.mark.asyncio
async def test_tool_gate_config_get_and_update():
    service = Mock(
        config=SimpleNamespace(
            enabled=True,
            rules=[
                SimpleNamespace(
                    id="common_knowledge",
                    enabled=True,
                    priority=10,
                    pattern="常识|定义",
                    flags="i",
                    include_tools=["web_search"],
                    exclude_tools=["execute_python", "execute_javascript"],
                    description="disable code tools for common questions",
                )
            ],
        )
    )
    service.save_config = Mock()

    response = await router.get_config(service=service)  # type: ignore[arg-type]
    assert response.enabled is True
    assert len(response.rules) == 1
    assert response.rules[0].id == "common_knowledge"

    updated = await router.update_config(
        router.ToolGateConfigUpdate(
            enabled=True,
            rules=[
                router.ToolGateRuleUpdate(
                    id="only_web",
                    enabled=True,
                    priority=5,
                    pattern="现在|最新",
                    flags="i",
                    include_tools=["web_search", "read_webpage"],
                    exclude_tools=["execute_python", "execute_javascript"],
                )
            ],
        ),
        service=service,  # type: ignore[arg-type]
    )
    assert updated["message"] == "Configuration updated successfully"
    service.save_config.assert_called_once()
    payload = service.save_config.call_args[0][0]
    assert payload["enabled"] is True
    assert payload["rules"][0]["id"] == "only_web"


@pytest.mark.asyncio
async def test_tool_gate_config_update_empty_payload_rejected():
    service = Mock(config=SimpleNamespace(enabled=False))
    service.save_config = Mock()

    with pytest.raises(HTTPException) as exc_info:
        await router.update_config(router.ToolGateConfigUpdate(), service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400
