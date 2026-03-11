from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone

import pytest

from src.api.models.async_run import AsyncRunRecord, RunStatus
from src.application.flow.async_run_service import AsyncRunService
from src.application.flow.flow_stream_runtime import FlowStreamRuntime


def _make_record(*, run_id: str, status: RunStatus) -> AsyncRunRecord:
    now = datetime.now(timezone.utc)
    return AsyncRunRecord(
        run_id=run_id,
        stream_id=run_id,
        kind="workflow",
        status=status,
        context_type="workflow",
        workflow_id="wf-test",
        created_at=now,
        updated_at=now,
    )


class _FakeStore:
    def __init__(self):
        self.saved_runs: list[AsyncRunRecord] = []

    async def save_run(self, record: AsyncRunRecord) -> None:
        self.saved_runs.append(record.model_copy(deep=True))


@pytest.mark.asyncio
async def test_reconcile_orphaned_runs_marks_non_terminal_runs_as_failed():
    store = _FakeStore()
    service = AsyncRunService(store=store, runtime=FlowStreamRuntime())
    record = _make_record(run_id="run-orphan", status="running")

    reconciled = await service.reconcile_orphaned_runs([record])

    assert reconciled[0].status == "failed"
    assert reconciled[0].finished_at is not None
    assert reconciled[0].error == "Run interrupted before completion. Please rerun."
    assert [item.run_id for item in store.saved_runs] == ["run-orphan"]


@pytest.mark.asyncio
async def test_reconcile_orphaned_runs_keeps_active_task_running():
    store = _FakeStore()
    service = AsyncRunService(store=store, runtime=FlowStreamRuntime())
    record = _make_record(run_id="run-active", status="running")
    task = asyncio.create_task(asyncio.sleep(10))
    service._tasks[record.run_id] = task

    try:
        reconciled = await service.reconcile_orphaned_runs([record])
        assert reconciled[0].status == "running"
        assert store.saved_runs == []
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
