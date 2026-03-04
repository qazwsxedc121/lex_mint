"""Async run orchestration service (workflow/chat background tasks)."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from ..models.async_run import AsyncRunRecord
from .async_run_store_service import AsyncRunStoreService
from .flow_event_emitter import FlowEventEmitter
from .flow_event_types import STREAM_ENDED
from .flow_stream_runtime import FlowStreamRuntime
from .workflow_config_service import WorkflowConfigService
from .workflow_execution_service import WorkflowExecutionService
from .workflow_flow_event_mapper import map_workflow_event_to_flow_payload


class AsyncRunService:
    """Create, execute, and control background async runs."""

    def __init__(
        self,
        *,
        store: Optional[AsyncRunStoreService] = None,
        runtime: Optional[FlowStreamRuntime] = None,
        workflow_config_service: Optional[WorkflowConfigService] = None,
        workflow_execution_service: Optional[WorkflowExecutionService] = None,
    ):
        self.store = store or AsyncRunStoreService()
        self.runtime = runtime or FlowStreamRuntime()
        self.workflow_config_service = workflow_config_service or WorkflowConfigService()
        self.workflow_execution_service = workflow_execution_service or WorkflowExecutionService()

        self._tasks: Dict[str, asyncio.Task[Any]] = {}
        self._cancel_flags: Dict[str, asyncio.Event] = {}

    async def create_workflow_run(
        self,
        *,
        workflow_id: str,
        inputs: Dict[str, Any],
        session_id: Optional[str] = None,
        context_type: Literal["workflow", "chat", "project"] = "workflow",
        project_id: Optional[str] = None,
        stream_mode: str = "default",
        artifact_target_path: Optional[str] = None,
        write_mode: Optional[Literal["none", "create", "overwrite"]] = None,
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

    async def get_run(self, run_id: str) -> Optional[AsyncRunRecord]:
        return await self.store.get_run(run_id)

    async def _run_workflow_task(
        self,
        *,
        record: AsyncRunRecord,
        workflow_id: str,
        inputs: Dict[str, Any],
        session_id: Optional[str],
        context_type: Literal["workflow", "chat", "project"],
        project_id: Optional[str],
        stream_mode: str,
        artifact_target_path: Optional[str],
        write_mode: Optional[Literal["none", "create", "overwrite"]],
        cancel_flag: asyncio.Event,
    ) -> None:
        if cancel_flag.is_set():
            record.status = "cancelled"
            now = datetime.now(timezone.utc)
            record.error = "Cancelled by user"
            record.updated_at = now
            record.finished_at = now
            await self.store.save_run(record)
            return

        workflow = await self.workflow_config_service.get_workflow(workflow_id)
        if workflow is None:
            record.status = "failed"
            record.error = f"Workflow '{workflow_id}' not found"
            record.updated_at = datetime.now(timezone.utc)
            record.finished_at = record.updated_at
            await self.store.save_run(record)
            return

        record.status = "running"
        record.started_at = datetime.now(timezone.utc)
        record.updated_at = record.started_at
        await self.store.save_run(record)

        emitter = FlowEventEmitter(
            stream_id=record.stream_id,
            conversation_id=record.run_id,
            default_turn_id=record.run_id,
            seq_provider=lambda: self.runtime.next_seq(record.stream_id),
        )

        terminal_emitted = False
        final_output: Optional[str] = None
        final_error: Optional[str] = None
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
        )

        started_payload = emitter.emit_started(context_type=context_type)
        self.runtime.append_payload(record.stream_id, started_payload)
        self._sync_record_cursor(record, started_payload)
        await self.store.save_run(record)

        try:
            async for event in stream:
                if cancel_flag.is_set():
                    record.status = "cancelled"
                    final_error = "Cancelled by user"
                    break

                payload = map_workflow_event_to_flow_payload(emitter, event)
                self.runtime.append_payload(record.stream_id, payload)
                self._sync_record_cursor(record, payload)

                flow_event = payload.get("flow_event")
                if isinstance(flow_event, dict):
                    event_type = str(flow_event.get("event_type") or "")
                    if event_type == "stream_error":
                        record.status = "failed"
                        final_error = str(flow_event.get("payload", {}).get("error") or "run failed")
                        terminal_emitted = True
                        break
                    if event_type == "workflow_run_finished":
                        status_value = str(flow_event.get("payload", {}).get("status") or "")
                        if status_value == "success":
                            record.status = "succeeded"
                        else:
                            record.status = "failed"
                        output_value = flow_event.get("payload", {}).get("output")
                        if isinstance(output_value, str):
                            final_output = output_value
                        terminal_emitted = True
                        break

                await self.store.save_run(record)
        except Exception as exc:
            record.status = "failed"
            final_error = str(exc)
            error_payload = emitter.emit_error(str(exc))
            self.runtime.append_payload(record.stream_id, error_payload)
            self._sync_record_cursor(record, error_payload)
            terminal_emitted = True
        finally:
            with contextlib.suppress(Exception):
                await stream.aclose()

            if record.status == "running":
                if cancel_flag.is_set():
                    record.status = "cancelled"
                    if not final_error:
                        final_error = "Cancelled by user"
                else:
                    record.status = "succeeded"
            now = datetime.now(timezone.utc)
            record.updated_at = now
            record.finished_at = now
            if final_output is not None:
                record.result_summary["output"] = final_output
            if final_error:
                record.error = final_error
                if record.status == "succeeded":
                    record.status = "failed"
            await self.store.save_run(record)

            if not terminal_emitted:
                ended_payload = emitter.emit_ended()
                self.runtime.append_payload(record.stream_id, ended_payload)
                self._sync_record_cursor(record, ended_payload)
                await self.store.save_run(record)
            else:
                # Keep transport contract stable for clients expecting stream_ended.
                state = self.runtime.get_stream(record.stream_id)
                events = list(state.events)
                has_stream_ended = False
                for payload in reversed(events):
                    flow_event = payload.get("flow_event")
                    if isinstance(flow_event, dict) and flow_event.get("event_type") == STREAM_ENDED:
                        has_stream_ended = True
                        break
                if not has_stream_ended:
                    ended_payload = emitter.emit_ended()
                    self.runtime.append_payload(record.stream_id, ended_payload)
                    self._sync_record_cursor(record, ended_payload)
                    await self.store.save_run(record)

    def _sync_record_cursor(self, record: AsyncRunRecord, payload: Dict[str, Any]) -> None:
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
