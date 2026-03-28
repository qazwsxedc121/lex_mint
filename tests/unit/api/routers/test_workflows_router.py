"""Unit tests for workflow router endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import HTTPException

from src.api.routers import workflows as workflows_router
from src.domain.models.async_run import AsyncRunRecord
from src.domain.models.workflow import (
    EndNode,
    LlmNode,
    StartNode,
    Workflow,
    WorkflowCreate,
    WorkflowRunRecord,
    WorkflowUpdate,
)


async def _collect_sse_payloads(streaming_response: Any) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    async for chunk in streaming_response.body_iterator:
        text = chunk.decode("utf-8") if isinstance(chunk, (bytes, bytearray)) else str(chunk)
        for line in text.splitlines():
            if line.startswith("data: "):
                payloads.append(json.loads(line[6:]))
    return payloads


def _workflow(
    *, workflow_id: str = "wf_1", enabled: bool = True, is_system: bool = False
) -> Workflow:
    now = datetime.now(timezone.utc)
    return Workflow(
        id=workflow_id,
        name="Workflow",
        description="demo",
        enabled=enabled,
        is_system=is_system,
        entry_node_id="start_1",
        nodes=[
            StartNode(id="start_1", type="start", next_id="llm_1"),
            LlmNode(id="llm_1", type="llm", prompt_template="Hello", next_id="end_1"),
            EndNode(id="end_1", type="end", result_template="{{ctx.last_output}}"),
        ],
        created_at=now,
        updated_at=now,
    )


def _workflow_create() -> WorkflowCreate:
    return WorkflowCreate(
        name="Workflow",
        description="demo",
        entry_node_id="start_1",
        nodes=[
            StartNode(id="start_1", type="start", next_id="llm_1"),
            LlmNode(id="llm_1", type="llm", prompt_template="Hello", next_id="end_1"),
            EndNode(id="end_1", type="end", result_template="{{ctx.last_output}}"),
        ],
    )


def _async_run_record(run_id: str = "run-1") -> AsyncRunRecord:
    now = datetime.now(timezone.utc)
    return AsyncRunRecord(
        run_id=run_id,
        stream_id=f"stream-{run_id}",
        kind="workflow",
        status="running",
        context_type="workflow",
        workflow_id="wf_1",
        created_at=now,
        updated_at=now,
        finished_at=None,
    )


def _history_record(run_id: str = "hist-1") -> WorkflowRunRecord:
    now = datetime.now(timezone.utc)
    return WorkflowRunRecord(
        run_id=run_id,
        workflow_id="wf_1",
        status="success",
        started_at=now,
        finished_at=now,
        duration_ms=1,
        output="done",
    )


class _WorkflowConfigService:
    def __init__(self) -> None:
        self.workflow = _workflow()
        self.added: Workflow | None = None
        self.updated: Workflow | None = None
        self.deleted: str | None = None
        self.fail_with: Exception | None = None

    async def get_workflows(self):
        return [self.workflow]

    async def get_workflow(self, workflow_id: str):
        if workflow_id == "missing":
            return None
        if workflow_id == "system":
            return _workflow(workflow_id="system", is_system=True)
        if workflow_id == "disabled":
            return _workflow(workflow_id="disabled", enabled=False)
        return self.workflow

    async def add_workflow(self, workflow: Workflow):
        if self.fail_with is not None:
            raise self.fail_with
        self.added = workflow

    async def update_workflow(self, workflow_id: str, workflow: Workflow):
        if self.fail_with is not None:
            raise self.fail_with
        self.updated = workflow
        self.workflow = workflow

    async def delete_workflow(self, workflow_id: str):
        if self.fail_with is not None:
            raise self.fail_with
        self.deleted = workflow_id


class _WorkflowHistoryService:
    def __init__(self) -> None:
        self.deleted: str | None = None
        self.record = _history_record()

    async def delete_runs(self, workflow_id: str):
        self.deleted = workflow_id

    async def list_runs(self, workflow_id: str, limit: int = 50):
        assert workflow_id
        assert limit
        return [self.record]

    async def get_run(self, workflow_id: str, run_id: str):
        assert workflow_id
        return None if run_id == "missing" else self.record


class _WorkflowExecutionService:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def execute_stream(self, workflow: Workflow, inputs: dict[str, Any], **kwargs):
        assert workflow.id
        assert isinstance(inputs, dict)
        _ = kwargs
        for event in self.events:
            yield event


class _AsyncRunService:
    def __init__(self) -> None:
        self.record = _async_run_record()
        self.fail_with: Exception | None = None

    async def create_workflow_run(self, **kwargs):
        if self.fail_with is not None:
            raise self.fail_with
        self.last_kwargs = kwargs
        return self.record


@pytest.mark.asyncio
async def test_workflow_router_crud_routes(monkeypatch):
    service = _WorkflowConfigService()
    history_service = _WorkflowHistoryService()
    monkeypatch.setattr(
        workflows_router.uuid, "uuid4", lambda: type("U", (), {"hex": "abcdef1234567890"})()
    )

    listed = await workflows_router.list_workflows(service=service)  # type: ignore[arg-type]
    assert listed[0].id == "wf_1"

    got = await workflows_router.get_workflow("wf_1", service=service)  # type: ignore[arg-type]
    assert got.id == "wf_1"

    created = await workflows_router.create_workflow(_workflow_create(), service=service)  # type: ignore[arg-type]
    assert created["id"] == "wf_abcdef123456"
    assert service.added is not None

    updated = await workflows_router.update_workflow(
        "wf_1",
        WorkflowUpdate(name="Updated"),
        service=service,  # type: ignore[arg-type]
    )
    assert updated["message"] == "Workflow updated successfully"
    assert service.updated and service.updated.name == "Updated"

    deleted = await workflows_router.delete_workflow(
        "wf_1",
        service=service,  # type: ignore[arg-type]
        history_service=history_service,  # type: ignore[arg-type]
    )
    assert deleted["message"] == "Workflow deleted successfully"
    assert history_service.deleted == "wf_1"

    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.get_workflow("missing", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.create_workflow(
            _workflow_create().model_copy(update={"is_system": True}),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.update_workflow(
            "missing",
            WorkflowUpdate(name="Updated"),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.update_workflow(
            "system",
            WorkflowUpdate(name="Updated"),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.delete_workflow(
            "system",
            service=service,  # type: ignore[arg-type]
            history_service=history_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 403

    service.fail_with = ValueError("bad workflow")
    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.create_workflow(_workflow_create(), service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.update_workflow(
            "wf_1",
            WorkflowUpdate(name="Updated"),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    service.fail_with = ValueError("missing workflow")
    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.delete_workflow(
            "wf_1",
            service=service,  # type: ignore[arg-type]
            history_service=history_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_validate_workflow_run_request_guards():
    disabled = _workflow(enabled=False)
    with pytest.raises(HTTPException) as exc_info:
        workflows_router._validate_workflow_run_request(
            disabled,
            workflows_router.WorkflowRunRequest(inputs={}),
        )
    assert exc_info.value.status_code == 409

    workflow = _workflow()
    for request, expected_status in [
        (workflows_router.WorkflowRunRequest(inputs={}, context_type="project"), 400),
        (workflows_router.WorkflowRunRequest(inputs={}, artifact_target_path="out.txt"), 400),
        (workflows_router.WorkflowRunRequest(inputs={}, write_mode="create"), 400),
    ]:
        with pytest.raises(HTTPException) as exc_info:
            workflows_router._validate_workflow_run_request(workflow, request)
        assert exc_info.value.status_code == expected_status


@pytest.mark.asyncio
async def test_workflow_run_routes_and_history(monkeypatch):
    service = _WorkflowConfigService()
    execution_service = _WorkflowExecutionService()
    execution_service.events = [
        {"type": "workflow_node_started", "node_id": "llm_1"},
        {"type": "workflow_run_finished", "result": "done"},
    ]
    run_service = _AsyncRunService()
    history_service = _WorkflowHistoryService()
    monkeypatch.setattr(workflows_router.uuid, "uuid4", lambda: "run-fixed")

    stream_response = await workflows_router.run_workflow_stream(
        "wf_1",
        workflows_router.WorkflowRunRequest(inputs={"topic": "x"}),
        service=service,  # type: ignore[arg-type]
        execution_service=execution_service,  # type: ignore[arg-type]
    )
    payloads = await _collect_sse_payloads(stream_response)
    assert payloads[0]["flow_event"]["event_type"] == "stream_started"
    assert payloads[-1]["flow_event"]["event_type"] == "stream_ended"

    execution_service.events = [{"type": "workflow_run_failed", "error": "boom"}]
    stream_response = await workflows_router.run_workflow_stream(
        "wf_1",
        workflows_router.WorkflowRunRequest(inputs={"topic": "x"}),
        service=service,  # type: ignore[arg-type]
        execution_service=execution_service,  # type: ignore[arg-type]
    )
    payloads = await _collect_sse_payloads(stream_response)
    assert any(payload["flow_event"]["event_type"] == "stream_error" for payload in payloads)

    created = await workflows_router.create_workflow_run(
        "wf_1",
        workflows_router.WorkflowRunRequest(inputs={"topic": "x"}, session_id="s1"),
        service=service,  # type: ignore[arg-type]
        run_service=run_service,  # type: ignore[arg-type]
    )
    assert created.run_id == "run-1"
    assert run_service.last_kwargs["workflow_id"] == "wf_1"

    listed = await workflows_router.list_workflow_runs(
        "wf_1",
        service=service,  # type: ignore[arg-type]
        history_service=history_service,  # type: ignore[arg-type]
    )
    assert listed[0].run_id == "hist-1"

    got = await workflows_router.get_workflow_run(
        "wf_1",
        "hist-1",
        service=service,  # type: ignore[arg-type]
        history_service=history_service,  # type: ignore[arg-type]
    )
    assert got.run_id == "hist-1"

    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.run_workflow_stream(
            "missing",
            workflows_router.WorkflowRunRequest(inputs={}),
            service=service,  # type: ignore[arg-type]
            execution_service=execution_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.create_workflow_run(
            "missing",
            workflows_router.WorkflowRunRequest(inputs={}),
            service=service,  # type: ignore[arg-type]
            run_service=run_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    run_service.fail_with = ValueError("invalid input")
    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.create_workflow_run(
            "wf_1",
            workflows_router.WorkflowRunRequest(inputs={}),
            service=service,  # type: ignore[arg-type]
            run_service=run_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.list_workflow_runs(
            "missing",
            service=service,  # type: ignore[arg-type]
            history_service=history_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.get_workflow_run(
            "wf_1",
            "missing",
            service=service,  # type: ignore[arg-type]
            history_service=history_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404
