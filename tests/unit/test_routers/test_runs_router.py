"""Unit tests for async run router endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest
from fastapi import HTTPException

from src.api.models.async_run import AsyncRunRecord, RunStatus
from src.api.routers import runs as runs_router
from src.api.services.flow_stream_runtime import FlowStreamRuntime


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
