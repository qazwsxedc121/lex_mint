"""Unit tests for workflow config and run history services."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.api.models.workflow import (
    LlmNode,
    StartNode,
    Workflow,
    WorkflowRunRecord,
)
from src.api.services.workflow_config_service import WorkflowConfigService
from src.api.services.workflow_run_history_service import WorkflowRunHistoryService


def _sample_workflow(workflow_id: str = "wf_demo") -> Workflow:
    now = datetime.now(timezone.utc)
    return Workflow(
        id=workflow_id,
        name="Demo Workflow",
        description="test",
        enabled=True,
        input_schema=[],
        entry_node_id="start_1",
        nodes=[
            StartNode(id="start_1", type="start", next_id="llm_1"),
            LlmNode(
                id="llm_1",
                type="llm",
                prompt_template="hello",
                next_id="end_1",
            ),
            {"id": "end_1", "type": "end"},
        ],
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_workflow_config_service_crud(temp_config_dir):
    config_path = Path(temp_config_dir) / "workflows_config.yaml"
    service = WorkflowConfigService(config_path=config_path)

    workflow = _sample_workflow("wf_demo")
    await service.add_workflow(workflow)

    loaded = await service.get_workflow("wf_demo")
    assert loaded is not None
    assert loaded.name == "Demo Workflow"

    updated = loaded.model_copy(update={"name": "Demo Workflow V2"})
    await service.update_workflow("wf_demo", updated)

    reloaded = await service.get_workflow("wf_demo")
    assert reloaded is not None
    assert reloaded.name == "Demo Workflow V2"

    await service.delete_workflow("wf_demo")
    assert await service.get_workflow("wf_demo") is None


@pytest.mark.asyncio
async def test_workflow_run_history_service_keeps_latest_n(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    service = WorkflowRunHistoryService(history_dir=history_dir, max_runs_per_workflow=3)

    for idx in range(5):
        now = datetime.now(timezone.utc)
        record = WorkflowRunRecord(
            run_id=f"run_{idx}",
            workflow_id="wf_demo",
            status="success",
            started_at=now,
            finished_at=now,
            duration_ms=1,
            inputs={"index": idx},
            output=f"output-{idx}",
            node_outputs={"last_output": f"output-{idx}"},
        )
        await service.append_run(record)

    runs = await service.list_runs("wf_demo", limit=50)
    assert len(runs) == 3
    assert runs[0].run_id == "run_4"
    assert runs[1].run_id == "run_3"
    assert runs[2].run_id == "run_2"


@pytest.mark.asyncio
async def test_workflow_config_service_ensures_system_workflows(temp_config_dir):
    config_path = Path(temp_config_dir) / "workflows_config.yaml"
    service = WorkflowConfigService(config_path=config_path)

    await service.ensure_system_workflows()
    workflows = await service.get_workflows()

    inline_rewrite = next(
        (workflow for workflow in workflows if workflow.id == service.INLINE_REWRITE_WORKFLOW_ID),
        None,
    )
    assert inline_rewrite is not None
    assert inline_rewrite.is_system is True
    assert inline_rewrite.scenario == "editor_rewrite"
