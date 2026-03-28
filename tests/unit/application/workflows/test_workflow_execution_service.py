"""Unit tests for workflow execution service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.application.workflows import WorkflowExecutionService
from src.application.workflows.run_history_service import WorkflowRunHistoryService
from src.domain.models.workflow import (
    ArtifactNode,
    ConditionNode,
    EndNode,
    LlmNode,
    StartNode,
    Workflow,
    WorkflowInputDef,
)


async def _fake_llm_stream(**_: Any) -> AsyncIterator[str | dict[str, Any]]:
    yield "hello "
    yield "world"
    yield {"type": "usage", "usage": {"completion_tokens": 2}}


class _FakeStorage:
    def __init__(self, session_payload: dict[str, Any]):
        self.session_payload = session_payload
        self.calls: list[dict[str, Any]] = []

    async def get_session(
        self, session_id: str, context_type: str = "chat", project_id: str | None = None
    ):
        self.calls.append(
            {
                "session_id": session_id,
                "context_type": context_type,
                "project_id": project_id,
            }
        )
        return self.session_payload


class _FakeProjectService:
    def __init__(self):
        self.files: dict[tuple[str, str], str] = {}

    async def read_file(self, project_id: str, relative_path: str):
        key = (project_id, relative_path)
        if key not in self.files:
            raise ValueError(f"Path does not exist: {relative_path}")
        content = self.files[key]
        return SimpleNamespace(
            content=content,
            content_hash=f"hash-{len(content)}",
            encoding="utf-8",
            size=len(content),
        )

    async def write_file(
        self,
        project_id: str,
        relative_path: str,
        content: str,
        encoding: str = "utf-8",
    ):
        key = (project_id, relative_path)
        self.files[key] = content
        return SimpleNamespace(
            content=content,
            content_hash=f"hash-{len(content)}",
            encoding=encoding,
            size=len(content),
        )


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


def _simple_rewrite_workflow() -> Workflow:
    now = datetime.now(timezone.utc)
    return Workflow(
        id="wf_rewrite_runtime",
        name="Rewrite Runtime",
        enabled=True,
        scenario="editor_rewrite",
        input_schema=[WorkflowInputDef(key="selected_text", type="string", required=True)],
        entry_node_id="start_1",
        nodes=[
            StartNode(id="start_1", type="start", next_id="llm_1"),
            LlmNode(
                id="llm_1", type="llm", prompt_template="{{inputs.selected_text}}", next_id="end_1"
            ),
            EndNode(id="end_1", type="end", result_template="{{ctx.last_output}}"),
        ],
        created_at=now,
        updated_at=now,
    )


def _artifact_workflow() -> Workflow:
    now = datetime.now(timezone.utc)
    return Workflow(
        id="wf_artifact_runtime",
        name="Artifact Runtime",
        enabled=True,
        scenario="project_pipeline",
        input_schema=[
            WorkflowInputDef(key="language", type="string", required=False, default="zh-CN")
        ],
        entry_node_id="start_1",
        nodes=[
            StartNode(id="start_1", type="start", next_id="llm_1"),
            LlmNode(
                id="llm_1",
                type="llm",
                prompt_template="draft",
                output_key="draft_doc",
                next_id="artifact_1",
            ),
            ArtifactNode(
                id="artifact_1",
                type="artifact",
                file_path_template="novel/00_charter.md",
                content_template="{{ctx.draft_doc}}",
                write_mode="overwrite",
                output_key="artifact_result",
                next_id="end_1",
            ),
            EndNode(id="end_1", type="end", result_template="{{ctx.last_artifact.file_path}}"),
        ],
        created_at=now,
        updated_at=now,
    )


def _chapter_artifact_workflow() -> Workflow:
    now = datetime.now(timezone.utc)
    return Workflow(
        id="wf_chapter_artifact_runtime",
        name="Chapter Artifact Runtime",
        enabled=True,
        scenario="project_pipeline",
        input_schema=[WorkflowInputDef(key="chapter_id", type="string", required=True)],
        entry_node_id="start_1",
        nodes=[
            StartNode(id="start_1", type="start", next_id="llm_1"),
            LlmNode(
                id="llm_1",
                type="llm",
                prompt_template="draft",
                output_key="draft_doc",
                next_id="artifact_1",
            ),
            ArtifactNode(
                id="artifact_1",
                type="artifact",
                file_path_template="novel/04_chapters/{{inputs.chapter_id}}_plan.md",
                content_template="{{ctx.draft_doc}}",
                write_mode="overwrite",
                output_key="artifact_result",
                next_id="end_1",
            ),
            EndNode(id="end_1", type="end", result_template="{{ctx.last_artifact.file_path}}"),
        ],
        created_at=now,
        updated_at=now,
    )


def _chapter_artifact_workflow_with_guard() -> Workflow:
    now = datetime.now(timezone.utc)
    return Workflow(
        id="wf_chapter_artifact_guard",
        name="Chapter Artifact Guard",
        enabled=True,
        scenario="project_pipeline",
        input_schema=[
            WorkflowInputDef(
                key="chapter_id",
                type="string",
                required=True,
                max_length=64,
                pattern=r'^[^\\/:*?"<>|\r\n]{1,64}$',
            )
        ],
        entry_node_id="start_1",
        nodes=[
            StartNode(id="start_1", type="start", next_id="llm_1"),
            LlmNode(
                id="llm_1",
                type="llm",
                prompt_template="draft",
                output_key="draft_doc",
                next_id="artifact_1",
            ),
            ArtifactNode(
                id="artifact_1",
                type="artifact",
                file_path_template="novel/04_chapters/{{inputs.chapter_id}}_plan.md",
                content_template="{{ctx.draft_doc}}",
                write_mode="overwrite",
                output_key="artifact_result",
                next_id="end_1",
            ),
            EndNode(id="end_1", type="end", result_template="{{ctx.last_artifact.file_path}}"),
        ],
        created_at=now,
        updated_at=now,
    )


def _workflow_with_node_input() -> Workflow:
    now = datetime.now(timezone.utc)
    return Workflow(
        id="wf_node_input",
        name="Node Input Test",
        enabled=True,
        input_schema=[
            WorkflowInputDef(key="target_node", type="node", required=True),
        ],
        entry_node_id="start_1",
        nodes=[
            StartNode(id="start_1", type="start", next_id="llm_1"),
            LlmNode(
                id="llm_1",
                type="llm",
                prompt_template="target={{inputs.target_node}}",
                next_id="end_1",
            ),
            EndNode(id="end_1", type="end", result_template="{{ctx.last_output}}"),
        ],
        created_at=now,
        updated_at=now,
    )


def _workflow_with_llm_reliability(
    *,
    timeout_ms: int | None = None,
    retry_count: int | None = None,
    retry_backoff_ms: int | None = None,
) -> Workflow:
    now = datetime.now(timezone.utc)
    return Workflow(
        id="wf_llm_reliability",
        name="LLM Reliability Test",
        enabled=True,
        input_schema=[WorkflowInputDef(key="topic", type="string", required=True)],
        entry_node_id="start_1",
        nodes=[
            StartNode(id="start_1", type="start", next_id="llm_1"),
            LlmNode(
                id="llm_1",
                type="llm",
                prompt_template="{{inputs.topic}}",
                timeout_ms=timeout_ms,
                retry_count=retry_count,
                retry_backoff_ms=retry_backoff_ms,
                next_id="end_1",
            ),
            EndNode(id="end_1", type="end", result_template="{{ctx.last_output}}"),
        ],
        created_at=now,
        updated_at=now,
    )


def test_workflow_input_def_node_default_requires_node_id_pattern():
    with pytest.raises(ValueError, match="node id pattern"):
        WorkflowInputDef(key="target_node", type="node", default="bad-id")


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
    async for event in service.execute_stream(
        workflow, {"topic": "python", "use_alt": False}, run_id="run_ok"
    ):
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
async def test_workflow_execution_service_condition_branch_routes_to_true_path(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    captured_prompt: dict[str, Any] = {}

    async def prompt_echo_stream(**kwargs: Any) -> AsyncIterator[str | dict[str, Any]]:
        messages = kwargs.get("messages") or []
        captured_prompt["content"] = str(messages[0].get("content") or "") if messages else ""
        yield captured_prompt["content"]

    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=prompt_echo_stream,
        max_steps=20,
    )
    workflow = _workflow_with_condition()

    events = []
    async for event in service.execute_stream(
        workflow,
        {"topic": "python", "use_alt": True},
        run_id="run_true_branch",
    ):
        events.append(event)

    assert captured_prompt["content"] == "alt python"
    assert events[-1]["type"] == "workflow_run_finished"
    assert events[-1]["output"] == "alt python"


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


@pytest.mark.asyncio
async def test_workflow_execution_service_accepts_node_input_type(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=_fake_llm_stream,
        max_steps=20,
    )
    workflow = _workflow_with_node_input()

    events = []
    async for event in service.execute_stream(
        workflow,
        {"target_node": "end_1"},
        run_id="run_node_input_ok",
    ):
        events.append(event)

    assert events[-1]["type"] == "workflow_run_finished"


@pytest.mark.asyncio
async def test_workflow_execution_service_rejects_unknown_node_input(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=_fake_llm_stream,
        max_steps=20,
    )
    workflow = _workflow_with_node_input()

    events = []
    async for event in service.execute_stream(
        workflow,
        {"target_node": "missing_node"},
        run_id="run_node_input_error",
    ):
        events.append(event)

    assert events[-1]["type"] == "stream_error"
    assert "unknown node id" in str(events[-1]["error"])


@pytest.mark.asyncio
async def test_workflow_execution_service_editor_rewrite_filters_think_and_uses_session_runtime(
    temp_config_dir, monkeypatch
):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    captured_kwargs: dict[str, Any] = {}

    async def fake_llm_stream(**kwargs: Any) -> AsyncIterator[str | dict[str, Any]]:
        captured_kwargs.update(kwargs)
        yield "<think>hidden "
        yield "internal</think>Hello"
        yield " world"
        yield {"type": "usage", "usage": {"completion_tokens": 2}}

    class FakeAssistantConfigService:
        async def get_assistant(self, _assistant_id: str):
            return SimpleNamespace(
                model_id="provider:assistant-model",
                system_prompt="assistant-system",
                temperature=0.2,
                max_tokens=2048,
                top_p=None,
                top_k=None,
                frequency_penalty=None,
                presence_penalty=None,
            )

    monkeypatch.setattr(
        "src.application.workflows.execution_service.AssistantConfigService",
        FakeAssistantConfigService,
    )

    storage = _FakeStorage(
        {
            "assistant_id": "assistant-1",
            "model_id": "provider:session-model",
            "param_overrides": {
                "model_id": "provider:override-model",
                "temperature": 0.5,
            },
        }
    )

    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=fake_llm_stream,
        storage=storage,  # type: ignore[arg-type]
        max_steps=10,
    )
    workflow = _simple_rewrite_workflow()

    text_chunks: list[str] = []
    events = []
    async for event in service.execute_stream(
        workflow,
        {"selected_text": "Original text"},
        run_id="run_editor_rewrite",
        session_id="session-1",
        context_type="project",
        project_id="proj-1",
        stream_mode="editor_rewrite",
    ):
        events.append(event)
        if event.get("type") == "text_delta":
            text_chunks.append(str(event.get("text") or ""))

    assert "".join(text_chunks) == "Hello world"
    assert captured_kwargs["model_id"] == "provider:override-model"
    assert captured_kwargs["temperature"] == 0.5
    assert captured_kwargs["max_tokens"] == 2048
    assert "assistant-system" == captured_kwargs["system_prompt"]
    assert storage.calls == [
        {"session_id": "session-1", "context_type": "project", "project_id": "proj-1"}
    ]
    assert events[-1]["type"] == "workflow_run_finished"
    assert events[-1]["output"] == "Hello world"

    runs = await history_service.list_runs(workflow.id)
    assert len(runs) == 1
    assert runs[0].output == "Hello world"


@pytest.mark.asyncio
async def test_workflow_execution_service_artifact_node_writes_project_file(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    project_service = _FakeProjectService()
    workflow = _artifact_workflow()

    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=_fake_llm_stream,
        project_service=project_service,  # type: ignore[arg-type]
        max_steps=10,
    )

    events = []
    async for event in service.execute_stream(
        workflow,
        {"language": "zh-CN"},
        run_id="run_artifact",
        context_type="project",
        project_id="proj-1",
        write_mode="create",
    ):
        events.append(event)

    artifact_event = next(
        (event for event in events if event.get("type") == "workflow_artifact_written"), None
    )
    assert artifact_event is not None
    assert artifact_event["file_path"] == "novel/00_charter.md"
    assert artifact_event["written"] is True

    assert project_service.files[("proj-1", "novel/00_charter.md")] == "hello world"

    runs = await history_service.list_runs(workflow.id)
    assert len(runs) == 1
    assert runs[0].status == "success"


@pytest.mark.asyncio
async def test_workflow_execution_service_artifact_path_rejects_document_content(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    project_service = _FakeProjectService()
    workflow = _chapter_artifact_workflow()

    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=_fake_llm_stream,
        project_service=project_service,  # type: ignore[arg-type]
        max_steps=10,
    )

    events = []
    async for event in service.execute_stream(
        workflow,
        {"chapter_id": "---\nartifact_type: charter\n"},
        run_id="run_invalid_artifact_path",
        context_type="project",
        project_id="proj-1",
        write_mode="overwrite",
    ):
        events.append(event)

    assert events[-1]["type"] == "stream_error"
    assert "invalid path characters" in str(events[-1]["error"])
    assert project_service.files == {}


@pytest.mark.asyncio
async def test_workflow_execution_service_input_feature_rejects_invalid_chapter_id(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    project_service = _FakeProjectService()
    workflow = _chapter_artifact_workflow_with_guard()

    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=_fake_llm_stream,
        project_service=project_service,  # type: ignore[arg-type]
        max_steps=10,
    )

    events = []
    async for event in service.execute_stream(
        workflow,
        {"chapter_id": "---\nartifact_type: charter\n"},
        run_id="run_invalid_chapter_id",
        context_type="project",
        project_id="proj-1",
        write_mode="overwrite",
    ):
        events.append(event)

    assert events[-1]["type"] == "stream_error"
    assert "format is invalid" in str(events[-1]["error"])
    assert project_service.files == {}


@pytest.mark.asyncio
async def test_workflow_execution_service_retries_transient_llm_errors(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    attempts = {"count": 0}

    async def flaky_llm_stream(**_: Any) -> AsyncIterator[str | dict[str, Any]]:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("upstream timeout")
        yield "recovered"

    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=flaky_llm_stream,
        default_llm_retry_count=0,
        default_llm_retry_backoff_ms=0,
        max_steps=10,
    )
    workflow = _workflow_with_llm_reliability(retry_count=1, retry_backoff_ms=0)

    events = []
    async for event in service.execute_stream(
        workflow,
        {"topic": "x"},
        run_id="run_retry_ok",
    ):
        events.append(event)

    assert attempts["count"] == 2
    retry_event = next(
        (event for event in events if event.get("type") == "workflow_node_retrying"), None
    )
    assert retry_event is not None
    assert retry_event["attempt"] == 2
    assert events[-1]["type"] == "workflow_run_finished"
    assert events[-1]["output"] == "recovered"


@pytest.mark.asyncio
async def test_workflow_execution_service_does_not_retry_after_partial_output(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    attempts = {"count": 0}

    async def flaky_after_text(**_: Any) -> AsyncIterator[str | dict[str, Any]]:
        attempts["count"] += 1
        yield "partial"
        raise TimeoutError("broken stream")

    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=flaky_after_text,
        default_llm_retry_count=0,
        default_llm_retry_backoff_ms=0,
        max_steps=10,
    )
    workflow = _workflow_with_llm_reliability(retry_count=2, retry_backoff_ms=0)

    events = []
    async for event in service.execute_stream(
        workflow,
        {"topic": "x"},
        run_id="run_partial_no_retry",
    ):
        events.append(event)

    assert attempts["count"] == 1
    assert all(event.get("type") != "workflow_node_retrying" for event in events)
    assert events[-1]["type"] == "stream_error"
    assert "broken stream" in str(events[-1]["error"])


@pytest.mark.asyncio
async def test_workflow_execution_service_honors_llm_timeout_and_retry_budget(temp_config_dir):
    history_dir = Path(temp_config_dir) / "workflow_runs"
    history_service = WorkflowRunHistoryService(history_dir=history_dir)
    attempts = {"count": 0}

    async def slow_llm_stream(**_: Any) -> AsyncIterator[str | dict[str, Any]]:
        attempts["count"] += 1
        await asyncio.sleep(0.05)
        yield "too-late"

    service = WorkflowExecutionService(
        history_service=history_service,
        llm_stream_fn=slow_llm_stream,
        default_llm_retry_count=0,
        default_llm_retry_backoff_ms=0,
        max_steps=10,
    )
    workflow = _workflow_with_llm_reliability(
        timeout_ms=10,
        retry_count=1,
        retry_backoff_ms=0,
    )

    events = []
    async for event in service.execute_stream(
        workflow,
        {"topic": "x"},
        run_id="run_timeout_exhausted",
    ):
        events.append(event)

    assert attempts["count"] == 2
    retry_events = [event for event in events if event.get("type") == "workflow_node_retrying"]
    assert len(retry_events) == 1
    assert events[-1]["type"] == "stream_error"
    assert "timed out after 10 ms" in str(events[-1]["error"])
