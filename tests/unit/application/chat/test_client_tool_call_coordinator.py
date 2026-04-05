"""Tests for client-side tool call coordination."""

from __future__ import annotations

import asyncio

import pytest

from src.application.chat.client_tool_call_coordinator import ClientToolCallCoordinator


@pytest.mark.asyncio
async def test_submit_before_await_is_buffered():
    coordinator = ClientToolCallCoordinator()
    await coordinator.submit_result(session_id="s1", tool_call_id="t1", result="ok")

    result = await coordinator.await_result(session_id="s1", tool_call_id="t1", timeout_s=0.2)
    assert result == "ok"


@pytest.mark.asyncio
async def test_await_then_submit_unblocks_waiter():
    coordinator = ClientToolCallCoordinator()

    async def _wait() -> str:
        return await coordinator.await_result(session_id="s1", tool_call_id="t2", timeout_s=1.0)

    waiter = asyncio.create_task(_wait())
    await asyncio.sleep(0)
    await coordinator.submit_result(session_id="s1", tool_call_id="t2", result="done")
    assert await waiter == "done"


@pytest.mark.asyncio
async def test_await_result_times_out():
    coordinator = ClientToolCallCoordinator()
    with pytest.raises(asyncio.TimeoutError):
        await coordinator.await_result(session_id="s1", tool_call_id="missing", timeout_s=0.01)
