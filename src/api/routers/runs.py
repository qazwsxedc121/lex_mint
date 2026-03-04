"""Unified async run management endpoints."""

from __future__ import annotations

import json
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..models.async_run import AsyncRunListResponse, AsyncRunRecord, RunKind, RunStatus
from ..services.async_run_provider import get_async_run_service, get_async_run_store
from ..services.async_run_service import AsyncRunService
from ..services.async_run_store_service import AsyncRunStoreService
from ..services.flow_event_emitter import FlowEventEmitter
from ..services.flow_event_types import REPLAY_FINISHED, RESUME_STARTED
from ..services.flow_events import FlowEventStage
from ..services.flow_stream_runtime import (
    FlowReplayCursorGoneError,
    FlowStreamContextMismatchError,
    FlowStreamNotFoundError,
    FlowStreamRuntime,
)
from ..services.flow_stream_runtime_provider import get_flow_stream_runtime

router = APIRouter(prefix="/api/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    """Create one async run."""

    kind: RunKind
    workflow_id: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    context_type: Literal["workflow", "chat", "project"] = "workflow"
    project_id: Optional[str] = None
    stream_mode: Literal["default", "editor_rewrite"] = "default"
    artifact_target_path: Optional[str] = None
    write_mode: Optional[Literal["none", "create", "overwrite"]] = None


class ResumeRunStreamRequest(BaseModel):
    """Resume one run stream from a known cursor."""

    last_event_id: str


def _is_terminal_payload(payload: Dict[str, Any]) -> bool:
    flow_event = payload.get("flow_event")
    if isinstance(flow_event, dict):
        event_type = flow_event.get("event_type")
        if event_type in {"stream_error", "stream_ended"}:
            return True
    return payload.get("done") is True or "error" in payload


@router.post("", response_model=AsyncRunRecord, status_code=201)
async def create_run(
    request: CreateRunRequest,
    service: AsyncRunService = Depends(get_async_run_service),
):
    if request.kind == "workflow":
        workflow_id = (request.workflow_id or "").strip()
        if not workflow_id:
            raise HTTPException(status_code=400, detail="workflow_id is required for workflow runs")
        try:
            return await service.create_workflow_run(
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
            message = str(exc)
            if "not found" in message.lower():
                raise HTTPException(status_code=404, detail=message) from exc
            if "disabled" in message.lower():
                raise HTTPException(status_code=409, detail=message) from exc
            raise HTTPException(status_code=400, detail=message) from exc

    raise HTTPException(status_code=400, detail="Unsupported run kind")


@router.get("", response_model=AsyncRunListResponse)
async def list_runs(
    limit: int = Query(default=50, ge=1, le=200),
    kind: Optional[RunKind] = Query(default=None),
    status: Optional[RunStatus] = Query(default=None),
    context_type: Optional[str] = Query(default=None),
    project_id: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    workflow_id: Optional[str] = Query(default=None),
    store: AsyncRunStoreService = Depends(get_async_run_store),
):
    runs = await store.list_runs(
        limit=limit,
        kind=kind,
        status=status,
        context_type=context_type,
        project_id=project_id,
        session_id=session_id,
        workflow_id=workflow_id,
    )
    return AsyncRunListResponse(runs=runs)


@router.get("/{run_id}", response_model=AsyncRunRecord)
async def get_run(run_id: str, store: AsyncRunStoreService = Depends(get_async_run_store)):
    run = await store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run


@router.post("/{run_id}/cancel", response_model=AsyncRunRecord)
async def cancel_run(
    run_id: str,
    service: AsyncRunService = Depends(get_async_run_service),
):
    try:
        return await service.cancel_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    store: AsyncRunStoreService = Depends(get_async_run_store),
    runtime: FlowStreamRuntime = Depends(get_flow_stream_runtime),
):
    run = await store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    try:
        state = runtime.get_stream(run.stream_id)
    except FlowStreamNotFoundError:
        # Process-level runtime was reset. Return synthetic ended stream for completed runs.
        if run.status in {"succeeded", "failed", "cancelled"}:
            emitter = FlowEventEmitter(stream_id=run.stream_id, conversation_id=run_id)

            async def completed_generator():
                started = emitter.emit_started(context_type=run.context_type)
                yield f"data: {json.dumps(started, ensure_ascii=False, default=str)}\n\n"
                if run.error:
                    error_payload = emitter.emit_error(run.error)
                    yield f"data: {json.dumps(error_payload, ensure_ascii=False, default=str)}\n\n"
                ended = emitter.emit_ended()
                yield f"data: {json.dumps(ended, ensure_ascii=False, default=str)}\n\n"

            return StreamingResponse(
                completed_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
        raise HTTPException(status_code=404, detail={"code": "stream_not_found", "message": "stream not found"})

    replay_payloads = list(state.events)
    subscriber_id, queue = runtime.subscribe(run.stream_id)

    async def event_generator():
        try:
            for payload in replay_payloads:
                yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                if _is_terminal_payload(payload):
                    return

            if state.done:
                return

            while True:
                payload = await queue.get()
                yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                if _is_terminal_payload(payload):
                    return
        finally:
            runtime.unsubscribe(run.stream_id, subscriber_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/{run_id}/stream/resume")
async def resume_run_stream(
    run_id: str,
    request: ResumeRunStreamRequest,
    store: AsyncRunStoreService = Depends(get_async_run_store),
    runtime: FlowStreamRuntime = Depends(get_flow_stream_runtime),
):
    run = await store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    try:
        subscriber_id, queue, replay_payloads = runtime.resume_subscribe(
            stream_id=run.stream_id,
            last_event_id=request.last_event_id,
            conversation_id=run.run_id,
            context_type=run.context_type,
            project_id=run.project_id,
        )
    except FlowStreamNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "stream_not_found", "message": "stream not found"})
    except FlowReplayCursorGoneError:
        raise HTTPException(
            status_code=410,
            detail={"code": "replay_cursor_gone", "message": "last_event_id is outside replay window"},
        )
    except FlowStreamContextMismatchError:
        raise HTTPException(
            status_code=409,
            detail={"code": "stream_context_mismatch", "message": "stream context does not match request"},
        )

    async def event_generator():
        resume_emitter = FlowEventEmitter(
            stream_id=run.stream_id,
            conversation_id=run.run_id,
            seq_provider=lambda: runtime.next_seq(run.stream_id),
        )
        try:
            started = resume_emitter.emit(
                event_type=RESUME_STARTED,
                stage=FlowEventStage.TRANSPORT,
                payload={"last_event_id": request.last_event_id},
            )
            yield f"data: {json.dumps(started, ensure_ascii=False, default=str)}\n\n"

            for payload in replay_payloads:
                yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                if _is_terminal_payload(payload):
                    return

            replay_done = resume_emitter.emit(
                event_type=REPLAY_FINISHED,
                stage=FlowEventStage.TRANSPORT,
                payload={"replayed_count": len(replay_payloads)},
            )
            yield f"data: {json.dumps(replay_done, ensure_ascii=False, default=str)}\n\n"

            while True:
                payload = await queue.get()
                yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                if _is_terminal_payload(payload):
                    return
        finally:
            runtime.unsubscribe(run.stream_id, subscriber_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
