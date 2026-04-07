"""Tests for code execution config router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from src.api.routers import code_execution_config as router


@pytest.mark.asyncio
async def test_code_execution_config_get_and_update():
    service = Mock(config=SimpleNamespace(enable_server_side_tool_execution=False))
    service.save_config = Mock()

    response = await router.get_config(service=service)  # type: ignore[arg-type]
    assert response.enable_server_side_tool_execution is False

    updated = await router.update_config(
        router.CodeExecutionConfigUpdate(enable_server_side_tool_execution=True),
        service=service,  # type: ignore[arg-type]
    )
    assert updated["message"] == "Configuration updated successfully"
    service.save_config.assert_called_once_with({"enable_server_side_tool_execution": True})


@pytest.mark.asyncio
async def test_code_execution_config_update_empty_payload_rejected():
    service = Mock(config=SimpleNamespace(enable_server_side_tool_execution=False))
    service.save_config = Mock()

    with pytest.raises(HTTPException) as exc_info:
        await router.update_config(router.CodeExecutionConfigUpdate(), service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400
