"""Tests for code execution config router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from src.api.routers import code_execution_config as router


@pytest.mark.asyncio
async def test_code_execution_config_get_and_update():
    service = Mock(
        config=SimpleNamespace(
            enable_client_tool_execution=True,
            enable_server_jupyter_execution=False,
            enable_server_subprocess_execution=True,
            execution_priority=["client", "server_subprocess", "server_jupyter"],
            jupyter_kernel_name="python3",
        )
    )
    service.save_config = Mock()

    response = await router.get_config(service=service)  # type: ignore[arg-type]
    assert response.enable_client_tool_execution is True
    assert response.enable_server_jupyter_execution is False
    assert response.enable_server_subprocess_execution is True
    assert response.execution_priority == ["client", "server_subprocess", "server_jupyter"]
    assert response.enable_server_side_tool_execution is True
    assert response.server_side_execution_backend == "subprocess"
    assert response.jupyter_kernel_name == "python3"

    updated = await router.update_config(
        router.CodeExecutionConfigUpdate(
            enable_client_tool_execution=True,
            enable_server_jupyter_execution=True,
            enable_server_subprocess_execution=False,
            execution_priority=["server_jupyter", "client", "server_subprocess"],
            jupyter_kernel_name="python3",
        ),
        service=service,  # type: ignore[arg-type]
    )
    assert updated["message"] == "Configuration updated successfully"
    service.save_config.assert_called_once_with(
        {
            "enable_client_tool_execution": True,
            "enable_server_jupyter_execution": True,
            "enable_server_subprocess_execution": False,
            "execution_priority": ["server_jupyter", "client", "server_subprocess"],
            "jupyter_kernel_name": "python3",
        }
    )


@pytest.mark.asyncio
async def test_code_execution_config_update_empty_payload_rejected():
    service = Mock(config=SimpleNamespace(enable_client_tool_execution=True))
    service.save_config = Mock()

    with pytest.raises(HTTPException) as exc_info:
        await router.update_config(router.CodeExecutionConfigUpdate(), service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_code_execution_config_update_invalid_backend_rejected():
    service = Mock(config=SimpleNamespace(enable_client_tool_execution=True))
    service.save_config = Mock()

    with pytest.raises(HTTPException) as exc_info:
        await router.update_config(
            router.CodeExecutionConfigUpdate(server_side_execution_backend="bad-backend"),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_code_execution_config_update_invalid_priority_rejected():
    service = Mock(config=SimpleNamespace(enable_client_tool_execution=True))
    service.save_config = Mock()

    with pytest.raises(HTTPException) as exc_info:
        await router.update_config(
            router.CodeExecutionConfigUpdate(
                execution_priority=["client", "bad_method"]  # type: ignore[list-item]
            ),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400
