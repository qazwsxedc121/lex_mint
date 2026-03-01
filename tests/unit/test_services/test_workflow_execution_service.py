"""Unit tests for workflow execution service."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Union

import pytest

from src.api.models.workflow import (
    ConditionNode,
    EndNode,
    LlmNode,
    StartNode,
    Workflow,
    WorkflowInputDef,
)
from src.api.services.workflow_execution_service import WorkflowExecutionService
from src.api.services.workflow_run_history_service import WorkflowRunHistoryService


async def _fake_llm_stream(**_: Any) -> AsyncIterator[Union[str, Dict[str, Any]]]:
    yield "hello "
    yield "world"
    yield {"type": "usage", "usage": {"completion_tokens": 2}}


def _workflow_with_condition() -> Workflow:
    now = datetime.now(timezone.utc)
    return Workflow(
        id="wf_exec",
        name="Execution Test",
        enabled=True,
        input_schema=[
            WorkflowInputDef(key="topic", type="string", required=True),
            WorkflowInputDef(key="use_alt", type="boolean", required=False, default=False),
        ],
        entry_node_id="start_1",
        nodes=[
            StartNode(id="start_1", type="start", next_id="cond_1"),
            ConditionNode(
                id="cond_1",
                type="condition",
                expression="inputs.use_alt == true",
                true_next_id="llm_alt",
                false_next_id="llm_main",
            ),
            LlmNode(
                id="llm_main",
                type="llm",
                prompt_template="main {{inputs.topic}}",
                output_key="main_output",
                next_id="end_1",
            ),
            LlmNode(
                id="llm_alt",
                type="llm",
                prompt_template="alt {{inputs.topic}}",
                output_key="alt_output",
                next_id="end_1",
            ),
            EndNode(id="end_1", type="end", result_template="{{ctx.last_output}}"),
        ],
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_workflow_execution_service_success(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=_fake_llm_stream,
        max_steps=20,
    )
    workflow = _workflow_with_condition()

    events = []
    async for event in service.execute_stream(workflow, {"topic": "python", "use_alt": False}, run_id="run_ok"):
        events.append(event)

    event_types = [event.get("type") for event in events]
    assert "workflow_run_started" in event_types
    assert "workflow_condition_evaluated" in event_types
    assert "text_delta" in event_types
    assert "workflow_run_finished" in event_types
    assert "stream_error" not in event_types

    runs = await history_service.list_runs(workflow.id)
    assert len(runs) == 1
    assert runs[0].status == "success"
    assert runs[0].run_id == "run_ok"
    assert runs[0].output == "hello world"


@pytest.mark.asyncio
async def test_workflow_execution_service_input_validation_error(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=_fake_llm_stream,
        max_steps=20,
    )
    workflow = _workflow_with_condition()

    events = []
    async for event in service.execute_stream(workflow, {"use_alt": False}, run_id="run_error"):
        events.append(event)

    assert events[-1]["type"] == "stream_error"
    assert "Missing required input 'topic'" in str(events[-1]["error"])

    runs = await history_service.list_runs(workflow.id)
    assert len(runs) == 1
    assert runs[0].status == "error"
    assert runs[0].run_id == "run_error"
