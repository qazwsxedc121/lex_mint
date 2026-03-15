from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone

import pytest

from src.domain.models.async_run import AsyncRunRecord, RunStatus
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
        self.run_map: dict[str, AsyncRunRecord] = {}

    async def save_run(self, record: AsyncRunRecord) -> None:
        copied = record.model_copy(deep=True)
        self.saved_runs.append(copied)
        self.run_map[copied.run_id] = copied

    async def get_run(self, run_id: str) -> AsyncRunRecord | None:
        record = self.run_map.get(run_id)
        return record.model_copy(deep=True) if record else None


class _FakeWorkflowConfigService:
    def __init__(self, workflow):
        self.workflow = workflow

    async def get_workflow(self, workflow_id: str):
        if self.workflow and getattr(self.workflow, "id", None) == workflow_id:
            return self.workflow
        return None


class _FakeWorkflowExecutionService:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    async def execute_stream(self, workflow, inputs, **kwargs):
        self.calls.append({"workflow": workflow, "inputs": inputs, **kwargs})
        yield {"type": "workflow_run_started", "workflow_id": getattr(workflow, "id", "wf"), "run_id": kwargs.get("run_id"), "checkpoint_id": "cp-1"}
        yield {"type": "workflow_run_finished", "workflow_id": getattr(workflow, "id", "wf"), "run_id": kwargs.get("run_id"), "status": "success", "output": "ok", "checkpoint_id": "cp-2"}


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


@pytest.mark.asyncio
async def test_resume_workflow_run_restarts_task_with_checkpoint_id():
    store = _FakeStore()
    runtime = FlowStreamRuntime()
    record = _make_record(run_id="run-resume", status="failed")
    record.workflow_id = "wf-test"
    record.context_type = "workflow"
    record.request_payload = {
        "inputs": {"topic": "x"},
        "session_id": "session-1",
        "context_type": "workflow",
        "project_id": None,
        "stream_mode": "default",
        "checkpoint_id": "cp-latest",
    }
    store.run_map[record.run_id] = record.model_copy(deep=True)
    workflow = type("WorkflowObj", (), {"id": "wf-test", "enabled": True})()
    execution_service = _FakeWorkflowExecutionService()
    service = AsyncRunService(
        store=store,
        runtime=runtime,
        workflow_config_service=_FakeWorkflowConfigService(workflow),  # type: ignore[arg-type]
        workflow_execution_service=execution_service,  # type: ignore[arg-type]
    )

    resumed = await service.resume_workflow_run("run-resume")
    await asyncio.gather(*service._tasks.values())

    assert resumed.status in {"running", "succeeded"}
    assert execution_service.calls
    assert execution_service.calls[0]["resume_from_checkpoint_id"] == "cp-latest"
    saved = store.run_map["run-resume"]
    assert saved.status == "succeeded"
    assert saved.result_summary.get("last_checkpoint_id") == "cp-2"

    state = runtime.get_stream("run-resume")
    flow_events = [
        payload.get("flow_event", {})
        for payload in state.events
        if isinstance(payload.get("flow_event"), dict)
    ]
    workflow_started = next(item for item in flow_events if item.get("event_type") == "workflow_run_started")
    workflow_finished = next(item for item in flow_events if item.get("event_type") == "workflow_run_finished")
    assert workflow_started.get("payload", {}).get("checkpoint_id") == "cp-1"
    assert workflow_finished.get("payload", {}).get("checkpoint_id") == "cp-2"
