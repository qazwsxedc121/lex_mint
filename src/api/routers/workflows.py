"""Workflow management and execution API endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.application.workflows import WorkflowExecutionService

from ..models.async_run import AsyncRunRecord
from ..models.workflow import Workflow, WorkflowCreate, WorkflowRunRecord, WorkflowUpdate
from ..services.async_run_provider import get_async_run_service
from ..services.async_run_service import AsyncRunService
from ..services.flow_event_emitter import FlowEventEmitter
from ..services.flow_event_types import (
    STREAM_ERROR,
)
from ..services.workflow_config_service import WorkflowConfigService
from ..services.workflow_flow_event_mapper import map_workflow_event_to_flow_payload
from ..services.workflow_run_history_service import WorkflowRunHistoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

_workflow_config_service = WorkflowConfigService()
_workflow_run_history_service = WorkflowRunHistoryService()
_workflow_execution_service = WorkflowExecutionService(
    history_service=_workflow_run_history_service
)


class WorkflowRunRequest(BaseModel):
    """Request body for workflow execution."""

    inputs: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    context_type: Literal["workflow", "chat", "project"] = "workflow"
    project_id: Optional[str] = None
    stream_mode: Literal["default", "editor_rewrite"] = "default"
    artifact_target_path: Optional[str] = None
    write_mode: Optional[Literal["none", "create", "overwrite"]] = None


def get_workflow_config_service() -> WorkflowConfigService:
    return _workflow_config_service


def get_workflow_run_history_service() -> WorkflowRunHistoryService:
    return _workflow_run_history_service


def get_workflow_execution_service() -> WorkflowExecutionService:
    return _workflow_execution_service


def _validate_workflow_run_request(workflow: Workflow, request: WorkflowRunRequest) -> None:
    if not workflow.enabled:
        raise HTTPException(status_code=409, detail="Workflow is disabled")
    if request.context_type == "project" and not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required when context_type is 'project'")
    if request.artifact_target_path and request.context_type != "project":
        raise HTTPException(
            status_code=400,
            detail="artifact_target_path requires context_type='project'",
        )
    if request.write_mode and request.context_type != "project":
        raise HTTPException(
            status_code=400,
            detail="write_mode requires context_type='project'",
        )


@router.get("", response_model=List[Workflow])
async def list_workflows(
    service: WorkflowConfigService = Depends(get_workflow_config_service),
):
    workflows = await service.get_workflows()
    return sorted(workflows, key=lambda item: item.updated_at, reverse=True)


@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow(
    workflow_id: str,
    service: WorkflowConfigService = Depends(get_workflow_config_service),
):
    workflow = await service.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return workflow


@router.post("", status_code=201)
async def create_workflow(
    payload: WorkflowCreate,
    service: WorkflowConfigService = Depends(get_workflow_config_service),
):
    if payload.is_system:
        raise HTTPException(status_code=403, detail="System workflows cannot be created via API")

    now = datetime.now(timezone.utc)
    workflow_id = payload.id or f"wf_{uuid.uuid4().hex[:12]}"

    workflow = Workflow(
        id=workflow_id,
        name=payload.name,
        description=payload.description,
        enabled=payload.enabled,
        scenario=payload.scenario,
        is_system=False,
        template_version=payload.template_version,
        input_schema=payload.input_schema,
        entry_node_id=payload.entry_node_id,
        nodes=payload.nodes,
        created_at=now,
        updated_at=now,
    )
    try:
        await service.add_workflow(workflow)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Workflow created successfully", "id": workflow_id}


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    service: WorkflowConfigService = Depends(get_workflow_config_service),
):
    existing = await service.get_workflow(workflow_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    if existing.is_system:
        raise HTTPException(status_code=403, detail="System workflows cannot be modified")

    merged = existing.model_dump(mode="python")
    for key, value in payload.model_dump(exclude_unset=True).items():
        merged[key] = value
    merged["updated_at"] = datetime.now(timezone.utc)

    try:
        updated = Workflow(**merged)
        await service.update_workflow(workflow_id, updated)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"message": "Workflow updated successfully"}


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    service: WorkflowConfigService = Depends(get_workflow_config_service),
    history_service: WorkflowRunHistoryService = Depends(get_workflow_run_history_service),
):
    existing = await service.get_workflow(workflow_id)
    if existing and existing.is_system:
        raise HTTPException(status_code=403, detail="System workflows cannot be deleted")

    try:
        await service.delete_workflow(workflow_id)
        await history_service.delete_runs(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Workflow deleted successfully"}


@router.post("/{workflow_id}/run/stream")
async def run_workflow_stream(
    workflow_id: str,
    request: WorkflowRunRequest,
    service: WorkflowConfigService = Depends(get_workflow_config_service),
    execution_service: WorkflowExecutionService = Depends(get_workflow_execution_service),
):
    workflow = await service.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    _validate_workflow_run_request(workflow, request)

    run_id = str(uuid.uuid4())
    emitter = FlowEventEmitter(stream_id=run_id, conversation_id=workflow_id, default_turn_id=run_id)

    async def event_generator():
        started_payload = emitter.emit_started(context_type=request.context_type)
        yield f"data: {json.dumps(started_payload, ensure_ascii=False, default=str)}\n\n"
        saw_terminal = False
        async for event in execution_service.execute_stream(
            workflow,
            request.inputs,
            run_id=run_id,
            session_id=request.session_id,
            context_type=request.context_type,
            project_id=request.project_id,
            stream_mode=request.stream_mode,
            artifact_target_path=request.artifact_target_path,
            write_mode=request.write_mode,
        ):
            payload = map_workflow_event_to_flow_payload(emitter, event)
            yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

            flow_event = payload.get("flow_event")
            if isinstance(flow_event, dict) and flow_event.get("event_type") == STREAM_ERROR:
                saw_terminal = True
                return

            if event.get("type") == "workflow_run_finished":
                ended_payload = emitter.emit_ended()
                yield f"data: {json.dumps(ended_payload, ensure_ascii=False, default=str)}\n\n"
                saw_terminal = True
                return

        if not saw_terminal:
            ended_payload = emitter.emit_ended()
            yield f"data: {json.dumps(ended_payload, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/{workflow_id}/runs", response_model=AsyncRunRecord, status_code=201)
async def create_workflow_run(
    workflow_id: str,
    request: WorkflowRunRequest,
    service: WorkflowConfigService = Depends(get_workflow_config_service),
    run_service: AsyncRunService = Depends(get_async_run_service),
):
    workflow = await service.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    _validate_workflow_run_request(workflow, request)

    try:
        return await run_service.create_workflow_run(
            workflow_id=workflow_id,
            inputs=request.inputs,
            session_id=request.session_id,
            context_type=request.context_type,
            project_id=request.project_id,
            stream_mode=request.stream_mode,
            artifact_target_path=request.artifact_target_path,
            write_mode=request.write_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{workflow_id}/runs", response_model=List[WorkflowRunRecord])
async def list_workflow_runs(
    workflow_id: str,
    limit: int = Query(default=50, ge=1, le=50),
    service: WorkflowConfigService = Depends(get_workflow_config_service),
    history_service: WorkflowRunHistoryService = Depends(get_workflow_run_history_service),
):
    workflow = await service.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return await history_service.list_runs(workflow_id, limit=limit)


@router.get("/{workflow_id}/runs/{run_id}", response_model=WorkflowRunRecord)
async def get_workflow_run(
    workflow_id: str,
    run_id: str,
    service: WorkflowConfigService = Depends(get_workflow_config_service),
    history_service: WorkflowRunHistoryService = Depends(get_workflow_run_history_service),
):
    workflow = await service.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    record = await history_service.get_run(workflow_id, run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return record
