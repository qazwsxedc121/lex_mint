"""Unit tests for async run router endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest
from fastapi import HTTPException

from src.api.models.async_run import AsyncRunRecord, RunStatus
from src.api.routers import runs as runs_router
from src.application.flow.flow_stream_runtime import FlowStreamRuntime


async def _collect_sse_payloads(streaming_response: Any) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    async for chunk in streaming_response.body_iterator:
        text = chunk.decode("utf-8") if isinstance(chunk, (bytes, bytearray)) else str(chunk)
        for line in text.splitlines():
            if not line.startswith("data: "):
                continue
            payloads.append(json.loads(line[6:]))
    return payloads


def _make_record(*, run_id: str, status: RunStatus, error: Optional[str] = None) -> AsyncRunRecord:
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
        finished_at=now if status in {"succeeded", "failed", "cancelled"} else None,
        error=error,
    )


class _FakeStore:
    def __init__(self, record: Optional[AsyncRunRecord]):
        self.record = record

    async def get_run(self, _run_id: str) -> Optional[AsyncRunRecord]:
        return self.record


class _FakeListStore:
    def __init__(self, runs: List[AsyncRunRecord]):
        self.runs = runs

    async def list_runs(self, **_kwargs) -> List[AsyncRunRecord]:
        return list(self.runs)


@pytest.mark.asyncio
async def test_create_run_requires_workflow_id_for_workflow_kind():
    class _UnusedService:
        async def create_workflow_run(self, **_kwargs):
            raise AssertionError("Should not be called without workflow_id")

    request = runs_router.CreateRunRequest(kind="workflow", inputs={"input": "x"})
    with pytest.raises(HTTPException) as exc_info:
        await runs_router.create_run(request=request, service=_UnusedService())
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_stream_run_returns_synthetic_terminal_payload_when_runtime_stream_missing():
    store = _FakeStore(_make_record(run_id="run-synthetic", status="failed", error="boom"))
    runtime = FlowStreamRuntime()

    response = await runs_router.stream_run(run_id="run-synthetic", store=store, runtime=runtime)
    payloads = await _collect_sse_payloads(response)

    flow_events = [item.get("flow_event") for item in payloads]
    assert [event.get("event_type") for event in flow_events] == [
        "stream_started",
        "stream_error",
        "stream_ended",
    ]
    assert flow_events[1]["payload"]["error"] == "boom"


@pytest.mark.asyncio
async def test_list_runs_applies_status_filter_after_reconcile():
    running_record = _make_record(run_id="run-orphan", status="running")
    store = _FakeListStore([running_record])

    class _ReconcilingService:
        async def reconcile_orphaned_runs(self, runs: List[AsyncRunRecord]) -> List[AsyncRunRecord]:
            runs[0].status = "failed"
            return runs

    response = await runs_router.list_runs(
        limit=50,
        kind=None,
        status="running",
        context_type=None,
        project_id=None,
        session_id=None,
        workflow_id=None,
        store=store,
        service=_ReconcilingService(),
    )

    assert response.runs == []
