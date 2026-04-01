"""Async run orchestration service (workflow/chat background tasks)."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, cast

from src.application.workflows import WorkflowExecutionService
from src.domain.models.async_run import AsyncRunRecord
from src.infrastructure.config.workflow_config_service import WorkflowConfigService
from src.infrastructure.storage.async_run_store_service import AsyncRunStoreService

from .flow_event_emitter import FlowEventEmitter
from .flow_event_types import STREAM_ENDED
from .flow_stream_runtime import FlowStreamRuntime
from .workflow_flow_event_mapper import map_workflow_event_to_flow_payload


@dataclass
class _RunTaskState:
    terminal_emitted: bool = False
    final_output: str | None = None
    final_error: str | None = None


class AsyncRunService:
    """Create, execute, and control background async runs."""

    def __init__(
        self,
        *,
        store: AsyncRunStoreService | None = None,
        runtime: FlowStreamRuntime | None = None,
        workflow_config_service: WorkflowConfigService | None = None,
        workflow_execution_service: WorkflowExecutionService | None = None,
    ):
        self.store = store or AsyncRunStoreService()
        self.runtime = runtime or FlowStreamRuntime()
        self.workflow_config_service = workflow_config_service or WorkflowConfigService()
        self.workflow_execution_service = workflow_execution_service or WorkflowExecutionService()

        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._cancel_flags: dict[str, asyncio.Event] = {}

    async def create_workflow_run(
        self,
        *,
        workflow_id: str,
        inputs: dict[str, Any],
        session_id: str | None = None,
        context_type: Literal["workflow", "chat", "project"] = "workflow",
        project_id: str | None = None,
        stream_mode: str = "default",
        artifact_target_path: str | None = None,
        write_mode: Literal["none", "create", "overwrite"] | None = None,
    ) -> AsyncRunRecord:
        """Create one background workflow run and return the queued record."""
        workflow = await self.workflow_config_service.get_workflow(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow '{workflow_id}' not found")
        if not workflow.enabled:
            raise ValueError("Workflow is disabled")
        if context_type == "project" and not project_id:
            raise ValueError("project_id is required when context_type is 'project'")
        if artifact_target_path and context_type != "project":
            raise ValueError("artifact_target_path requires context_type='project'")
        if write_mode and context_type != "project":
            raise ValueError("write_mode requires context_type='project'")

        now = datetime.now(timezone.utc)
        run_id = str(uuid.uuid4())
        stream_id = run_id
        record = AsyncRunRecord(
            run_id=run_id,
            stream_id=stream_id,
            kind="workflow",
            status="queued",
            context_type=context_type,
            project_id=project_id,
            session_id=session_id,
            workflow_id=workflow_id,
            created_at=now,
            updated_at=now,
            request_payload={
                "inputs": inputs,
                "session_id": session_id,
                "context_type": context_type,
                "project_id": project_id,
                "stream_mode": stream_mode,
                "artifact_target_path": artifact_target_path,
                "write_mode": write_mode,
            },
        )
        await self.store.save_run(record)

        try:
            self.runtime.create_stream(
                stream_id=stream_id,
                conversation_id=run_id,
                context_type=context_type,
                project_id=project_id,
            )
        except RuntimeError as exc:
            record.status = "failed"
            record.error = str(exc)
            record.updated_at = datetime.now(timezone.utc)
            record.finished_at = record.updated_at
            await self.store.save_run(record)
            return record

        cancel_flag = asyncio.Event()
        self._cancel_flags[run_id] = cancel_flag
        task = asyncio.create_task(
            self._run_workflow_task(
                record=record,
                workflow_id=workflow_id,
                inputs=inputs,
                session_id=session_id,
                context_type=context_type,
                project_id=project_id,
                stream_mode=stream_mode,
                artifact_target_path=artifact_target_path,
                write_mode=write_mode,
                cancel_flag=cancel_flag,
            )
        )
        self._tasks[run_id] = task
        task.add_done_callback(lambda _task: self._cleanup_task(run_id))
        return record

    async def cancel_run(self, run_id: str) -> AsyncRunRecord:
        """Request cancellation for a running/queued run."""
        record = await self.store.get_run(run_id)
        if record is None:
            raise ValueError(f"Run '{run_id}' not found")
        if record.status in {"succeeded", "failed", "cancelled"}:
            return record

        cancel_flag = self._cancel_flags.get(run_id)
        if cancel_flag is not None:
            cancel_flag.set()

        record.status = "cancelled"
        now = datetime.now(timezone.utc)
        record.error = "Cancelled by user"
        record.updated_at = now
        record.finished_at = now
        await self.store.save_run(record)
        return record

    async def resume_workflow_run(
        self,
        run_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> AsyncRunRecord:
        """Resume one workflow run from latest or explicit checkpoint."""
        record = await self.store.get_run(run_id)
        if record is None:
            raise ValueError(f"Run '{run_id}' not found")
        if record.kind != "workflow":
            raise ValueError("Only workflow runs support resume")
        if record.status in {"succeeded", "cancelled"}:
            raise ValueError(f"Run '{run_id}' is already terminal: {record.status}")
        if self._is_task_active(run_id):
            return record

        workflow_id = (record.workflow_id or "").strip()
        if not workflow_id:
            raise ValueError("Cannot resume run without workflow_id")

        workflow = await self.workflow_config_service.get_workflow(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow '{workflow_id}' not found")
        if not workflow.enabled:
            raise ValueError("Workflow is disabled")

        self.runtime.create_stream(
            stream_id=record.stream_id,
            conversation_id=record.run_id,
            context_type=record.context_type,
            project_id=record.project_id,
        )

        request_payload = dict(record.request_payload or {})
        resume_from_checkpoint_id = (
            checkpoint_id
            or request_payload.get("checkpoint_id")
            or record.result_summary.get("last_checkpoint_id")
        )
        if isinstance(resume_from_checkpoint_id, str):
            resume_from_checkpoint_id = resume_from_checkpoint_id.strip() or None
        else:
            resume_from_checkpoint_id = None

        cancel_flag = asyncio.Event()
        self._cancel_flags[run_id] = cancel_flag
        record.status = "running"
        record.error = None
        now = datetime.now(timezone.utc)
        record.started_at = record.started_at or now
        record.updated_at = now
        record.finished_at = None
        if resume_from_checkpoint_id:
            record.request_payload["checkpoint_id"] = resume_from_checkpoint_id
        await self.store.save_run(record)

        task = asyncio.create_task(
            self._run_workflow_task(
                record=record,
                workflow_id=workflow_id,
                inputs=request_payload.get("inputs", {}) or {},
                session_id=request_payload.get("session_id"),
                context_type=record.context_type,
                project_id=record.project_id,
                stream_mode=str(request_payload.get("stream_mode", "default") or "default"),
                artifact_target_path=request_payload.get("artifact_target_path"),
                write_mode=request_payload.get("write_mode"),
                cancel_flag=cancel_flag,
                resume_from_checkpoint_id=resume_from_checkpoint_id,
            )
        )
        self._tasks[run_id] = task
        task.add_done_callback(lambda _task: self._cleanup_task(run_id))
        return record

    async def get_run(self, run_id: str) -> AsyncRunRecord | None:
        return await self.store.get_run(run_id)

    async def reconcile_orphaned_runs(self, runs: list[AsyncRunRecord]) -> list[AsyncRunRecord]:
        """Mark queued/running runs as failed when this process has no active task."""
        reconciled: list[AsyncRunRecord] = []
        for record in runs:
            if record.status in {"queued", "running"} and not self._is_task_active(record.run_id):
                now = datetime.now(timezone.utc)
                record.status = "failed"
                record.error = record.error or "Run interrupted before completion. Please rerun."
                record.updated_at = now
                record.finished_at = now
                await self.store.save_run(record)
            reconciled.append(record)
        return reconciled

    async def _abort_before_run_if_needed(
        self,
        *,
        record: AsyncRunRecord,
        workflow_id: str,
        cancel_flag: asyncio.Event,
    ) -> Any | None:
        if cancel_flag.is_set():
            await self._mark_record_terminal(
                record,
                status="cancelled",
                error="Cancelled by user",
            )
            return None

        workflow = await self.workflow_config_service.get_workflow(workflow_id)
        if workflow is None:
            await self._mark_record_terminal(
                record,
                status="failed",
                error=f"Workflow '{workflow_id}' not found",
            )
            return None
        return workflow

    async def _mark_record_running(self, record: AsyncRunRecord) -> None:
        now = datetime.now(timezone.utc)
        record.status = "running"
        record.started_at = now
        record.updated_at = now
        record.finished_at = None
        record.error = None
        await self.store.save_run(record)

    def _build_emitter(self, record: AsyncRunRecord) -> FlowEventEmitter:
        return FlowEventEmitter(
            stream_id=record.stream_id,
            conversation_id=record.run_id,
            default_turn_id=record.run_id,
            seq_provider=lambda: self.runtime.next_seq(record.stream_id),
        )

    def _append_runtime_payload(
        self,
        *,
        record: AsyncRunRecord,
        payload: dict[str, Any],
    ) -> None:
        self.runtime.append_payload(record.stream_id, payload)
        self._sync_record_cursor(record, payload)

    async def _save_started_payload(
        self,
        *,
        record: AsyncRunRecord,
        emitter: FlowEventEmitter,
        context_type: Literal["workflow", "chat", "project"],
    ) -> None:
        started_payload = emitter.emit_started(context_type=context_type)
        self._append_runtime_payload(record=record, payload=started_payload)
        await self.store.save_run(record)

    def _update_checkpoint(self, record: AsyncRunRecord, event: dict[str, Any]) -> None:
        checkpoint_id = event.get("checkpoint_id")
        if isinstance(checkpoint_id, str) and checkpoint_id:
            record.result_summary["last_checkpoint_id"] = checkpoint_id

    def _apply_terminal_flow_event(
        self,
        *,
        record: AsyncRunRecord,
        payload: dict[str, Any],
        task_state: _RunTaskState,
    ) -> bool:
        flow_event = payload.get("flow_event")
        if not isinstance(flow_event, dict):
            return False

        event_type = str(flow_event.get("event_type") or "")
        if event_type == "stream_error":
            record.status = "failed"
            task_state.final_error = str(flow_event.get("payload", {}).get("error") or "run failed")
            task_state.terminal_emitted = True
            return True

        if event_type != "workflow_run_finished":
            return False

        status_value = str(flow_event.get("payload", {}).get("status") or "")
        record.status = "succeeded" if status_value == "success" else "failed"
        output_value = flow_event.get("payload", {}).get("output")
        if isinstance(output_value, str):
            task_state.final_output = output_value
        task_state.terminal_emitted = True
        return True

    async def _consume_workflow_stream(
        self,
        *,
        record: AsyncRunRecord,
        stream: Any,
        emitter: FlowEventEmitter,
        cancel_flag: asyncio.Event,
        task_state: _RunTaskState,
    ) -> None:
        try:
            async for event in stream:
                if cancel_flag.is_set():
                    record.status = "cancelled"
                    task_state.final_error = "Cancelled by user"
                    break

                self._update_checkpoint(record, event)
                payload = map_workflow_event_to_flow_payload(emitter, event)
                self._append_runtime_payload(record=record, payload=payload)
                if self._apply_terminal_flow_event(
                    record=record,
                    payload=payload,
                    task_state=task_state,
                ):
                    break
                await self.store.save_run(record)
        except Exception as exc:
            record.status = "failed"
            task_state.final_error = str(exc)
            error_payload = emitter.emit_error(str(exc))
            self._append_runtime_payload(record=record, payload=error_payload)
            task_state.terminal_emitted = True

    async def _close_stream(self, stream: Any) -> None:
        with contextlib.suppress(Exception):
            close_stream = getattr(stream, "aclose", None)
            if callable(close_stream):
                close_result = close_stream()
                if inspect.isawaitable(close_result):
                    await cast(Awaitable[Any], close_result)

    async def _mark_record_terminal(
        self,
        record: AsyncRunRecord,
        *,
        status: Literal["succeeded", "failed", "cancelled"],
        error: str | None = None,
        final_output: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        record.status = status
        record.updated_at = now
        record.finished_at = now
        record.error = error
        if final_output is not None:
            record.result_summary["output"] = final_output
        await self.store.save_run(record)

    async def _finalize_task_record(
        self,
        *,
        record: AsyncRunRecord,
        cancel_flag: asyncio.Event,
        task_state: _RunTaskState,
    ) -> None:
        status = record.status
        final_error = task_state.final_error
        if status == "running":
            if cancel_flag.is_set():
                status = "cancelled"
                final_error = final_error or "Cancelled by user"
            else:
                status = "succeeded"

        if final_error and status == "succeeded":
            status = "failed"

        await self._mark_record_terminal(
            record,
            status=cast(Literal["succeeded", "failed", "cancelled"], status),
            error=final_error,
            final_output=task_state.final_output,
        )

    def _stream_has_ended_payload(self, stream_id: str) -> bool:
        state = self.runtime.get_stream(stream_id)
        for payload in reversed(list(state.events)):
            flow_event = payload.get("flow_event")
            if isinstance(flow_event, dict) and flow_event.get("event_type") == STREAM_ENDED:
                return True
        return False

    async def _ensure_terminal_payload(
        self,
        *,
        record: AsyncRunRecord,
        emitter: FlowEventEmitter,
        terminal_emitted: bool,
    ) -> None:
        if terminal_emitted and self._stream_has_ended_payload(record.stream_id):
            return
        ended_payload = emitter.emit_ended()
        self._append_runtime_payload(record=record, payload=ended_payload)
        await self.store.save_run(record)

    async def _run_workflow_task(
        self,
        *,
        record: AsyncRunRecord,
        workflow_id: str,
        inputs: dict[str, Any],
        session_id: str | None,
        context_type: Literal["workflow", "chat", "project"],
        project_id: str | None,
        stream_mode: str,
        artifact_target_path: str | None,
        write_mode: Literal["none", "create", "overwrite"] | None,
        cancel_flag: asyncio.Event,
        resume_from_checkpoint_id: str | None = None,
    ) -> None:
        workflow = await self._abort_before_run_if_needed(
            record=record,
            workflow_id=workflow_id,
            cancel_flag=cancel_flag,
        )
        if workflow is None:
            return

        await self._mark_record_running(record)
        emitter = self._build_emitter(record)
        task_state = _RunTaskState()
        stream = self.workflow_execution_service.execute_stream(
            workflow,
            inputs,
            run_id=record.run_id,
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
            stream_mode=stream_mode,
            artifact_target_path=artifact_target_path,
            write_mode=write_mode,
            resume_from_checkpoint_id=resume_from_checkpoint_id,
        )

        await self._save_started_payload(
            record=record,
            emitter=emitter,
            context_type=context_type,
        )

        try:
            await self._consume_workflow_stream(
                record=record,
                stream=stream,
                emitter=emitter,
                cancel_flag=cancel_flag,
                task_state=task_state,
            )
        finally:
            await self._close_stream(stream)
            await self._finalize_task_record(
                record=record,
                cancel_flag=cancel_flag,
                task_state=task_state,
            )
            await self._ensure_terminal_payload(
                record=record,
                emitter=emitter,
                terminal_emitted=task_state.terminal_emitted,
            )

    def _sync_record_cursor(self, record: AsyncRunRecord, payload: dict[str, Any]) -> None:
        flow_event = payload.get("flow_event")
        if not isinstance(flow_event, dict):
            return
        event_id = flow_event.get("event_id")
        seq = flow_event.get("seq")
        if isinstance(event_id, str):
            record.last_event_id = event_id
        if isinstance(seq, int):
            record.last_seq = seq
        record.updated_at = datetime.now(timezone.utc)

    def _cleanup_task(self, run_id: str) -> None:
        self._tasks.pop(run_id, None)
        self._cancel_flags.pop(run_id, None)

    def _is_task_active(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        return task is not None and not task.done()
