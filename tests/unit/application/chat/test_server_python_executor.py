"""Tests for server-side Python executor backends."""

from __future__ import annotations

import json

import pytest

from src.application.chat.server_python_executor import execute_python_server_side_with_backend


@pytest.mark.asyncio
async def test_execute_python_server_side_unknown_backend_returns_error():
    result = await execute_python_server_side_with_backend(
        code="1+1",
        timeout_ms=30000,
        backend="unknown-backend",
        jupyter_kernel_name="python3",
    )
    payload = json.loads(result)
    assert payload["ok"] is False
    assert "Unknown server-side execution backend" in str(payload.get("error") or "")
