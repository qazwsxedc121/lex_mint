"""Unit tests for async run router endpoints."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, cast

import pytest
from fastapi import HTTPException

from src.api.routers import runs as runs_router
from src.application.flow.flow_stream_runtime import FlowStreamRuntime
from src.domain.models.async_run import AsyncRunRecord, RunStatus


async def _collect_sse_payloads(streaming_response: Any) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    async for chunk in streaming_response.body_iterator:
        text = chunk.decode("utf-8") if isinstance(chunk, (bytes, bytearray)) else str(chunk)
        for line in text.splitlines():
            if not line.startswith("data: "):
                continue
            payloads.append(json.loads(line[6:]))
    return payloads


def _make_record(*, run_id: str, status: RunStatus, error: str | None = None) -> AsyncRunRecord:
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
    def __init__(self, record: AsyncRunRecord | None):
        self.record = record

    async def get_run(self, _run_id: str) -> AsyncRunRecord | None:
        return self.record


class _FakeListStore:
    def __init__(self, runs: list[AsyncRunRecord]):
        self.runs = runs

    async def list_runs(self, **_kwargs) -> list[AsyncRunRecord]:
        return list(self.runs)


class _FakeResumeService:
    def __init__(self, record: AsyncRunRecord):
        self.record = record
        self.calls: list[dict[str, object]] = []
        self.error: ValueError | None = None

    async def resume_workflow_run(
        self, run_id: str, *, checkpoint_id: str | None = None
    ) -> AsyncRunRecord:
        if self.error is not None:
            raise self.error
        self.calls.append({"run_id": run_id, "checkpoint_id": checkpoint_id})
        return self.record


class _FakeCreateService:
    def __init__(self, record: AsyncRunRecord):
        self.record = record
        self.error: ValueError | None = None
        self.calls: list[dict[str, object]] = []

    async def create_workflow_run(self, **kwargs) -> AsyncRunRecord:
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)
        return self.record


class _FakeCancelService:
    def __init__(self, record: AsyncRunRecord):
        self.record = record
        self.error: ValueError | None = None

    async def cancel_run(self, run_id: str) -> AsyncRunRecord:
        if self.error is not None:
            raise self.error
        assert run_id == self.record.run_id
        return self.record


@pytest.mark.asyncio
async def test_create_run_requires_workflow_id_for_workflow_kind():
    class _UnusedService:
        async def create_workflow_run(self, **_kwargs):
            raise AssertionError("Should not be called without workflow_id")

    request = runs_router.CreateRunRequest(kind="workflow", inputs={"input": "x"})
    with pytest.raises(HTTPException) as exc_info:
        await runs_router.create_run(request=request, service=cast(Any, _UnusedService()))
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_run_success_and_error_mapping():
    service = _FakeCreateService(_make_record(run_id="run-create", status="running"))

    response = await runs_router.create_run(
        request=runs_router.CreateRunRequest(
            kind="workflow", workflow_id="wf-test", inputs={"x": 1}
        ),
        service=service,  # type: ignore[arg-type]
    )
    assert response.run_id == "run-create"
    assert service.calls[0]["workflow_id"] == "wf-test"

    for message, status_code in [
        ("workflow not found", 404),
        ("workflow disabled", 409),
        ("invalid inputs", 400),
    ]:
        service.error = ValueError(message)
        with pytest.raises(HTTPException) as exc_info:
            await runs_router.create_run(
                request=runs_router.CreateRunRequest(kind="workflow", workflow_id="wf-test"),
                service=service,  # type: ignore[arg-type]
            )
        assert exc_info.value.status_code == status_code

    with pytest.raises(HTTPException) as exc_info:
        await runs_router.create_run(
            request=runs_router.CreateRunRequest(kind="workflow", workflow_id="wf-test").model_copy(
                update={"kind": "chat"}
            ),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_stream_run_returns_synthetic_terminal_payload_when_runtime_stream_missing():
    store = _FakeStore(_make_record(run_id="run-synthetic", status="failed", error="boom"))
    runtime = FlowStreamRuntime()

    response = await runs_router.stream_run(
        run_id="run-synthetic", store=cast(Any, store), runtime=runtime
    )
    payloads = await _collect_sse_payloads(response)

    flow_events = [cast(dict[str, Any], item["flow_event"]) for item in payloads]
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
        async def reconcile_orphaned_runs(self, runs: list[AsyncRunRecord]) -> list[AsyncRunRecord]:
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
        store=cast(Any, store),
        service=cast(Any, _ReconcilingService()),
    )

    assert response.runs == []


@pytest.mark.asyncio
async def test_get_run_and_cancel_run_routes():
    record = _make_record(run_id="run-get", status="running")
    store = _FakeStore(record)

    class _ReconcilingService:
        async def reconcile_orphaned_runs(self, runs: list[AsyncRunRecord]) -> list[AsyncRunRecord]:
            return runs

    response = await runs_router.get_run(
        run_id="run-get",
        store=store,  # type: ignore[arg-type]
        service=_ReconcilingService(),  # type: ignore[arg-type]
    )
    assert response.run_id == "run-get"

    with pytest.raises(HTTPException) as exc_info:
        await runs_router.get_run(
            run_id="missing",
            store=_FakeStore(None),  # type: ignore[arg-type]
            service=_ReconcilingService(),  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    cancel_service = _FakeCancelService(record)
    cancelled = await runs_router.cancel_run("run-get", service=cancel_service)  # type: ignore[arg-type]
    assert cancelled.run_id == "run-get"

    cancel_service.error = ValueError("run missing")
    with pytest.raises(HTTPException) as exc_info:
        await runs_router.cancel_run("run-get", service=cancel_service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_stream_run_and_resume_stream_live_paths():
    record = _make_record(run_id="run-live", status="running")
    runtime = FlowStreamRuntime()
    runtime.create_stream(
        stream_id=record.stream_id,
        conversation_id=record.run_id,
        context_type="workflow",
        project_id=None,
    )
    emitter = runs_router.FlowEventEmitter(
        stream_id=record.stream_id, conversation_id=record.run_id
    )
    started = emitter.emit_started(context_type="workflow")
    runtime.append_payload(record.stream_id, started)

    response = await runs_router.stream_run(
        run_id="run-live",
        store=_FakeStore(record),  # type: ignore[arg-type]
        runtime=runtime,
    )
    collect_stream = asyncio.create_task(_collect_sse_payloads(response))
    await asyncio.sleep(0)
    runtime.append_payload(record.stream_id, emitter.emit_ended())
    payloads = await collect_stream
    assert payloads[0]["flow_event"]["event_type"] == "stream_started"

    runtime = FlowStreamRuntime()
    runtime.create_stream(
        stream_id=record.stream_id,
        conversation_id=record.run_id,
        context_type="workflow",
        project_id=None,
    )
    emitter = runs_router.FlowEventEmitter(
        stream_id=record.stream_id, conversation_id=record.run_id
    )
    started = emitter.emit_started(context_type="workflow")
    runtime.append_payload(record.stream_id, started)

    response = await runs_router.resume_run_stream(
        run_id="run-live",
        request=runs_router.ResumeRunStreamRequest(last_event_id=started["flow_event"]["event_id"]),
        store=_FakeStore(record),  # type: ignore[arg-type]
        runtime=runtime,
    )
    collect_resume = asyncio.create_task(_collect_sse_payloads(response))
    await asyncio.sleep(0)
    runtime.append_payload(record.stream_id, emitter.emit_ended())
    payloads = await collect_resume
    assert payloads[0]["flow_event"]["event_type"] == "resume_started"
    assert any(payload["flow_event"]["event_type"] == "replay_finished" for payload in payloads)


@pytest.mark.asyncio
async def test_resume_run_stream_error_mapping():
    record = _make_record(run_id="run-live", status="running")

    with pytest.raises(HTTPException) as exc_info:
        await runs_router.resume_run_stream(
            run_id="missing",
            request=runs_router.ResumeRunStreamRequest(last_event_id="evt-1"),
            store=_FakeStore(None),  # type: ignore[arg-type]
            runtime=FlowStreamRuntime(),
        )
    assert exc_info.value.status_code == 404

    class _MissingRuntime:
        def resume_subscribe(self, **_kwargs):
            raise runs_router.FlowStreamNotFoundError("missing")

    with pytest.raises(HTTPException) as exc_info:
        await runs_router.resume_run_stream(
            run_id="run-live",
            request=runs_router.ResumeRunStreamRequest(last_event_id="evt-1"),
            store=_FakeStore(record),  # type: ignore[arg-type]
            runtime=_MissingRuntime(),  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    class _GoneRuntime:
        def resume_subscribe(self, **_kwargs):
            raise runs_router.FlowReplayCursorGoneError("gone")

    with pytest.raises(HTTPException) as exc_info:
        await runs_router.resume_run_stream(
            run_id="run-live",
            request=runs_router.ResumeRunStreamRequest(last_event_id="evt-1"),
            store=_FakeStore(record),  # type: ignore[arg-type]
            runtime=_GoneRuntime(),  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 410

    class _MismatchRuntime:
        def resume_subscribe(self, **_kwargs):
            raise runs_router.FlowStreamContextMismatchError("mismatch")

    with pytest.raises(HTTPException) as exc_info:
        await runs_router.resume_run_stream(
            run_id="run-live",
            request=runs_router.ResumeRunStreamRequest(last_event_id="evt-1"),
            store=_FakeStore(record),  # type: ignore[arg-type]
            runtime=_MismatchRuntime(),  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_resume_run_endpoint_delegates_to_service():
    record = _make_record(run_id="run-resume", status="running")
    service = _FakeResumeService(record)

    response = await runs_router.resume_run(
        run_id="run-resume",
        request=runs_router.ResumeRunRequest(checkpoint_id="cp-1"),
        service=service,  # type: ignore[arg-type]
    )

    assert response.run_id == "run-resume"
    assert service.calls == [{"run_id": "run-resume", "checkpoint_id": "cp-1"}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "status_code"),
    [
        ("Run 'x' not found", 404),
        ("Run 'x' is already terminal: succeeded", 409),
        ("Only workflow runs support resume", 400),
    ],
)
async def test_resume_run_endpoint_maps_resume_errors_to_http(message: str, status_code: int):
    record = _make_record(run_id="run-resume", status="running")
    service = _FakeResumeService(record)
    service.error = ValueError(message)

    with pytest.raises(HTTPException) as exc_info:
        await runs_router.resume_run(
            run_id="run-resume",
            request=runs_router.ResumeRunRequest(),
            service=service,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == status_code
