"""Validation tests for workflow graph/static references."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.domain.models.workflow import (
    ConditionNode,
    EndNode,
    LlmNode,
    StartNode,
    Workflow,
    WorkflowInputDef,
)


def _now():
    return datetime.now(timezone.utc)


def test_workflow_rejects_unreachable_nodes():
    with pytest.raises(ValidationError, match="unreachable nodes"):
        Workflow(
            id="wf_unreachable",
            name="wf",
            enabled=True,
            input_schema=[WorkflowInputDef(key="topic", type="string", required=True)],
            entry_node_id="start_1",
            nodes=[
                StartNode(id="start_1", type="start", next_id="llm_1"),
                LlmNode(
                    id="llm_1",
                    type="llm",
                    prompt_template="{{inputs.topic}}",
                    next_id="end_1",
                ),
                EndNode(id="end_1", type="end"),
                EndNode(id="end_2", type="end"),
            ],
            created_at=_now(),
            updated_at=_now(),
        )


def test_workflow_rejects_cycles():
    with pytest.raises(ValidationError, match="contains a cycle"):
        Workflow(
            id="wf_cycle",
            name="wf",
            enabled=True,
            input_schema=[WorkflowInputDef(key="flag", type="boolean", required=False)],
            entry_node_id="start_1",
            nodes=[
                StartNode(id="start_1", type="start", next_id="llm_1"),
                LlmNode(id="llm_1", type="llm", prompt_template="x", next_id="cond_1"),
                ConditionNode(
                    id="cond_1",
                    type="condition",
                    expression="inputs.flag == true",
                    true_next_id="llm_1",
                    false_next_id="end_1",
                ),
                EndNode(id="end_1", type="end"),
            ],
            created_at=_now(),
            updated_at=_now(),
        )


def test_workflow_rejects_unknown_input_reference_in_template():
    with pytest.raises(ValidationError, match="unknown input 'missing'"):
        Workflow(
            id="wf_bad_template_input",
            name="wf",
            enabled=True,
            input_schema=[WorkflowInputDef(key="topic", type="string", required=True)],
            entry_node_id="start_1",
            nodes=[
                StartNode(id="start_1", type="start", next_id="llm_1"),
                LlmNode(
                    id="llm_1",
                    type="llm",
                    prompt_template="Topic: {{inputs.missing}}",
                    next_id="end_1",
                ),
                EndNode(id="end_1", type="end"),
            ],
            created_at=_now(),
            updated_at=_now(),
        )


def test_workflow_rejects_unknown_input_reference_in_condition():
    with pytest.raises(ValidationError, match="unknown input 'missing'"):
        Workflow(
            id="wf_bad_condition_input",
            name="wf",
            enabled=True,
            input_schema=[WorkflowInputDef(key="flag", type="boolean", required=False)],
            entry_node_id="start_1",
            nodes=[
                StartNode(id="start_1", type="start", next_id="cond_1"),
                ConditionNode(
                    id="cond_1",
                    type="condition",
                    expression="inputs.flag == true and inputs.missing == false",
                    true_next_id="end_1",
                    false_next_id="end_2",
                ),
                EndNode(id="end_1", type="end"),
                EndNode(id="end_2", type="end"),
            ],
            created_at=_now(),
            updated_at=_now(),
        )


def test_workflow_accepts_inputs_and_ctx_references():
    workflow = Workflow(
        id="wf_ok",
        name="wf",
        enabled=True,
        input_schema=[WorkflowInputDef(key="topic", type="string", required=True)],
        entry_node_id="start_1",
        nodes=[
            StartNode(id="start_1", type="start", next_id="llm_1"),
            LlmNode(
                id="llm_1",
                type="llm",
                prompt_template="Topic={{inputs.topic}} run={{ctx.run_id}}",
                next_id="end_1",
            ),
            EndNode(id="end_1", type="end", result_template="{{ctx.last_output}}"),
        ],
        created_at=_now(),
        updated_at=_now(),
    )

    assert workflow.id == "wf_ok"
