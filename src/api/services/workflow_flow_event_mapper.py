"""Helpers to map workflow runtime events to FlowEvent envelopes."""

from __future__ import annotations

from typing import Any, Dict

from .flow_event_emitter import FlowEventEmitter
from .flow_event_types import (
    LEGACY_EVENT,
    WORKFLOW_ARTIFACT_WRITTEN,
    WORKFLOW_CONDITION_EVALUATED,
    WORKFLOW_NODE_FINISHED,
    WORKFLOW_NODE_STARTED,
    WORKFLOW_OUTPUT_REPORTED,
    WORKFLOW_RUN_FINISHED,
    WORKFLOW_RUN_STARTED,
)
from .flow_events import FlowEventStage


def map_workflow_event_to_flow_payload(
    emitter: FlowEventEmitter,
    event: Dict[str, Any],
) -> Dict[str, Any]:
    """Convert workflow runtime event to canonical flow payload."""
    event_type = str(event.get("type") or "")

    if event_type == "workflow_run_started":
        return emitter.emit(
            event_type=WORKFLOW_RUN_STARTED,
            stage=FlowEventStage.ORCHESTRATION,
            payload={
                "workflow_id": event.get("workflow_id"),
                "run_id": event.get("run_id"),
            },
        )

    if event_type == "workflow_node_started":
        return emitter.emit(
            event_type=WORKFLOW_NODE_STARTED,
            stage=FlowEventStage.ORCHESTRATION,
            payload={
                "workflow_id": event.get("workflow_id"),
                "run_id": event.get("run_id"),
                "node_id": event.get("node_id"),
                "node_type": event.get("node_type"),
            },
        )

    if event_type == "text_delta":
        return emitter.emit_text_delta(
            str(event.get("text") or ""),
            payload={
                "workflow_id": event.get("workflow_id"),
                "run_id": event.get("run_id"),
                "node_id": event.get("node_id"),
            },
        )

    if event_type == "workflow_condition_evaluated":
        return emitter.emit(
            event_type=WORKFLOW_CONDITION_EVALUATED,
            stage=FlowEventStage.ORCHESTRATION,
            payload={
                "workflow_id": event.get("workflow_id"),
                "run_id": event.get("run_id"),
                "node_id": event.get("node_id"),
                "expression": event.get("expression"),
                "result": event.get("result"),
            },
        )

    if event_type == "workflow_node_finished":
        return emitter.emit(
            event_type=WORKFLOW_NODE_FINISHED,
            stage=FlowEventStage.ORCHESTRATION,
            payload={
                "workflow_id": event.get("workflow_id"),
                "run_id": event.get("run_id"),
                "node_id": event.get("node_id"),
                "node_type": event.get("node_type"),
                "result": event.get("result"),
                "output_key": event.get("output_key"),
                "output": event.get("output"),
                "usage": event.get("usage"),
            },
        )

    if event_type == "workflow_output_reported":
        return emitter.emit(
            event_type=WORKFLOW_OUTPUT_REPORTED,
            stage=FlowEventStage.META,
            payload={
                "workflow_id": event.get("workflow_id"),
                "run_id": event.get("run_id"),
                "node_id": event.get("node_id"),
                "output": event.get("output"),
            },
        )

    if event_type == "workflow_artifact_written":
        return emitter.emit(
            event_type=WORKFLOW_ARTIFACT_WRITTEN,
            stage=FlowEventStage.META,
            payload={
                "workflow_id": event.get("workflow_id"),
                "run_id": event.get("run_id"),
                "node_id": event.get("node_id"),
                "file_path": event.get("file_path"),
                "write_mode": event.get("write_mode"),
                "written": event.get("written"),
                "output_key": event.get("output_key"),
                "content_hash": event.get("content_hash"),
            },
        )

    if event_type == "workflow_run_finished":
        return emitter.emit(
            event_type=WORKFLOW_RUN_FINISHED,
            stage=FlowEventStage.ORCHESTRATION,
            payload={
                "workflow_id": event.get("workflow_id"),
                "run_id": event.get("run_id"),
                "status": event.get("status"),
                "output": event.get("output"),
            },
        )

    if event_type == "stream_error":
        return emitter.emit_error(str(event.get("error") or "workflow stream error"))

    return emitter.emit(
        event_type=LEGACY_EVENT,
        stage=FlowEventStage.META,
        payload={"legacy_type": event_type, "data": event},
    )

