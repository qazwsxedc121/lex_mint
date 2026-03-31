"""Workflow runtime execution service."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import (
    Any,
    Literal,
    cast,
)

from src.application.orchestration import (
    ActorEmit,
    ActorExecutionContext,
    ActorRef,
    ActorResult,
    EdgeSpec,
    InMemoryContextManager,
    NodeSpec,
    OrchestrationEngine,
    RetryPolicy,
    RunContext,
    RunSpec,
)
from src.application.workflows.run_history_service import WorkflowRunHistoryService
from src.core.config import settings
from src.domain.models.workflow import (
    ArtifactNode,
    ConditionNode,
    EndNode,
    LlmNode,
    StartNode,
    Workflow,
    WorkflowRunRecord,
)
from src.infrastructure.config.assistant_config_service import AssistantConfigService
from src.infrastructure.config.project_service import ProjectService
from src.infrastructure.storage.conversation_storage import (
    ConversationStorage,
    create_storage_with_project_resolver,
)
from src.llm_runtime import call_llm_stream
from src.llm_runtime.think_tag_filter import ThinkTagStreamFilter

_TEMPLATE_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*}}")
_NODE_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_WINDOWS_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_INVALID_ARTIFACT_PATH_CHAR_RE = re.compile(r'[\x00-\x1f<>:"|?*]')


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str


@dataclass
class _ResolvedRuntimeConfig:
    model_id: str | None
    system_prompt: str | None
    generation_params: dict[str, Any]


@dataclass
class _WorkflowRunState:
    run_id: str
    workflow: Workflow
    inputs: dict[str, Any]
    ctx: dict[str, Any]
    runtime: _ResolvedRuntimeConfig
    session_id: str | None
    context_type: str
    project_id: str | None
    stream_mode: str
    artifact_target_path: str | None
    write_mode: Literal["none", "create", "overwrite"] | None


@dataclass
class _ExecutionProgress:
    normalized_inputs: dict[str, Any]
    ctx: dict[str, Any]
    output_text: str | None = None
    status: str = "error"
    error_message: str | None = None


class _ConditionParser:
    """Small parser/evaluator for safe condition expressions."""

    _TOKEN_RE = re.compile(
        r"""
        (?P<SPACE>\s+)
        |(?P<LPAREN>\()
        |(?P<RPAREN>\))
        |(?P<OP>==|!=|>=|<=|>|<)
        |(?P<AND>\band\b)
        |(?P<OR>\bor\b)
        |(?P<NOT>\bnot\b)
        |(?P<BOOL>\btrue\b|\bfalse\b)
        |(?P<NUMBER>-?\d+(?:\.\d+)?)
        |(?P<STRING>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
        |(?P<IDENT>[A-Za-z_][A-Za-z0-9_.]*)
        |(?P<MISMATCH>.)
        """,
        re.VERBOSE,
    )

    def __init__(self, expression: str, context: dict[str, Any]):
        self.tokens = self._tokenize(expression)
        self.pos = 0
        self.context = context

    def _tokenize(self, expression: str) -> list[_Token]:
        tokens: list[_Token] = []
        for match in self._TOKEN_RE.finditer(expression):
            kind = match.lastgroup
            value = match.group()
            if kind == "SPACE":
                continue
            if kind == "MISMATCH":
                raise ValueError(f"Invalid token '{value}' in condition expression")
            if kind is None:
                continue
            tokens.append(_Token(kind=kind, value=value))
        return tokens

    def _peek(self) -> _Token | None:
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def _consume(self, expected_kind: str | None = None) -> _Token:
        token = self._peek()
        if token is None:
            raise ValueError("Unexpected end of expression")
        if expected_kind is not None and token.kind != expected_kind:
            raise ValueError(f"Expected {expected_kind}, got {token.kind}")
        self.pos += 1
        return token

    def parse(self) -> bool:
        value = self._parse_or_expr()
        trailing_token = self._peek()
        if trailing_token is not None:
            raise ValueError(f"Unexpected token '{trailing_token.value}'")
        return bool(value)

    def _parse_or_expr(self) -> Any:
        value = self._parse_and_expr()
        while True:
            token = self._peek()
            if token is None or token.kind != "OR":
                break
            self._consume("OR")
            right = self._parse_and_expr()
            value = bool(value) or bool(right)
        return value

    def _parse_and_expr(self) -> Any:
        value = self._parse_not_expr()
        while True:
            token = self._peek()
            if token is None or token.kind != "AND":
                break
            self._consume("AND")
            right = self._parse_not_expr()
            value = bool(value) and bool(right)
        return value

    def _parse_not_expr(self) -> Any:
        token = self._peek()
        if token is not None and token.kind == "NOT":
            self._consume("NOT")
            return not bool(self._parse_not_expr())
        return self._parse_comparison()

    def _parse_comparison(self) -> Any:
        left = self._parse_term()
        token = self._peek()
        if token is None or token.kind != "OP":
            return left
        op = self._consume("OP").value
        right = self._parse_term()
        return self._compare(left, op, right)

    @staticmethod
    def _compare(left: Any, op: str, right: Any) -> bool:
        if op == "==":
            return bool(left == right)
        if op == "!=":
            return bool(left != right)
        if op == ">":
            return bool(left > right)
        if op == "<":
            return bool(left < right)
        if op == ">=":
            return bool(left >= right)
        if op == "<=":
            return bool(left <= right)
        raise ValueError(f"Unsupported operator '{op}'")

    def _parse_term(self) -> Any:
        token = self._peek()
        if token is None:
            raise ValueError("Expected a value, got end of expression")

        if token.kind == "LPAREN":
            self._consume("LPAREN")
            value = self._parse_or_expr()
            self._consume("RPAREN")
            return value

        if token.kind == "NUMBER":
            raw = self._consume("NUMBER").value
            return float(raw) if "." in raw else int(raw)

        if token.kind == "STRING":
            raw = self._consume("STRING").value
            return bytes(raw[1:-1], "utf-8").decode("unicode_escape")

        if token.kind == "BOOL":
            return self._consume("BOOL").value.lower() == "true"

        if token.kind == "IDENT":
            identifier = self._consume("IDENT").value
            return _resolve_context_path(self.context, identifier)

        raise ValueError(f"Unexpected token '{token.value}'")


def _resolve_context_path(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise ValueError(f"Unknown variable '{path}' in condition expression")
    return current


class WorkflowExecutionService:
    """Execute workflow definitions and emit runtime events."""

    _PARAM_KEYS = (
        "temperature",
        "max_tokens",
        "top_p",
        "top_k",
        "frequency_penalty",
        "presence_penalty",
    )

    def __init__(
        self,
        *,
        history_service: WorkflowRunHistoryService | None = None,
        orchestration_engine: OrchestrationEngine | None = None,
        llm_stream_fn: Callable[..., AsyncIterator[str | dict[str, Any]]] | None = None,
        storage: ConversationStorage | None = None,
        project_service: ProjectService | None = None,
        max_steps: int = 100,
        default_llm_timeout_ms: int | None = 180000,
        default_llm_retry_count: int = 1,
        default_llm_retry_backoff_ms: int = 300,
        max_llm_retry_backoff_ms: int = 5000,
    ):
        self.history_service = history_service or WorkflowRunHistoryService()
        self.orchestration_engine = orchestration_engine or OrchestrationEngine()
        self.llm_stream_fn = llm_stream_fn or call_llm_stream
        self.storage = storage or create_storage_with_project_resolver(settings.conversations_dir)
        self.project_service = project_service or ProjectService()
        self.max_steps = max(1, int(max_steps))
        self.default_llm_timeout_ms = (
            None if default_llm_timeout_ms is None else max(1, int(default_llm_timeout_ms))
        )
        self.default_llm_retry_count = max(0, int(default_llm_retry_count))
        self.default_llm_retry_backoff_ms = max(0, int(default_llm_retry_backoff_ms))
        self.max_llm_retry_backoff_ms = max(0, int(max_llm_retry_backoff_ms))

    def _build_checkpoint_payload(self, runtime_event: dict[str, Any]) -> dict[str, Any]:
        checkpoint_id = runtime_event.get("checkpoint_id")
        if isinstance(checkpoint_id, str) and checkpoint_id:
            return {"checkpoint_id": checkpoint_id}
        return {}

    def _runtime_stream(
        self,
        *,
        run_spec: RunSpec,
        run_context: RunContext,
        resume_from_checkpoint_id: str | None,
    ) -> AsyncIterator[dict[str, Any]]:
        if resume_from_checkpoint_id:
            return self.orchestration_engine.resume_stream(
                run_spec,
                context=run_context,
                from_checkpoint_id=resume_from_checkpoint_id,
            )
        return self.orchestration_engine.run_stream(run_spec, run_context)

    def _build_run_context(
        self,
        *,
        run_id: str,
        workflow: Workflow,
        context_type: str,
        project_id: str | None,
        resume_from_checkpoint_id: str | None,
    ) -> RunContext:
        return RunContext(
            run_id=run_id,
            metadata={
                "workflow_id": workflow.id,
                "context_type": context_type,
                "project_id": project_id or "",
                "resume": bool(resume_from_checkpoint_id),
            },
            max_steps=self.max_steps,
            context_manager=InMemoryContextManager(),
        )

    async def _append_run_record(
        self,
        *,
        workflow: Workflow,
        run_identifier: str,
        started_at: datetime,
        progress: _ExecutionProgress,
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        record = WorkflowRunRecord(
            run_id=run_identifier,
            workflow_id=workflow.id,
            status="success" if progress.status == "success" else "error",
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            inputs=progress.normalized_inputs,
            output=progress.output_text,
            node_outputs=progress.ctx,
            error=progress.error_message,
        )
        await self.history_service.append_run(record)

    def _require_runtime_node(
        self,
        *,
        workflow: Workflow,
        node_map: dict[str, Any],
        runtime_event: dict[str, Any],
    ) -> Any:
        node_id = str(runtime_event.get("node_id") or "")
        node = node_map.get(node_id)
        if node is None:
            raise ValueError(f"Unknown runtime node '{node_id}'")
        return node

    @staticmethod
    def _runtime_payload(runtime_event: dict[str, Any]) -> dict[str, Any]:
        payload = runtime_event.get("payload") or {}
        return payload if isinstance(payload, dict) else {}

    def _translate_runtime_event(
        self,
        *,
        workflow: Workflow,
        run_identifier: str,
        runtime_event: dict[str, Any],
        node_map: dict[str, Any],
        run_state: _WorkflowRunState,
        progress: _ExecutionProgress,
    ) -> dict[str, Any] | None:
        event_type = str(runtime_event.get("type") or "")
        checkpoint_payload = self._build_checkpoint_payload(runtime_event)

        if event_type == "resumed":
            progress.ctx["resumed_from_checkpoint_id"] = runtime_event.get("checkpoint_id")
            progress.ctx["resume_step"] = runtime_event.get("step")
            return None
        if event_type == "started":
            return self._workflow_run_started_event(
                workflow=workflow,
                run_identifier=run_identifier,
                checkpoint_payload=checkpoint_payload,
            )
        if event_type == "node_started":
            node = self._require_runtime_node(
                workflow=workflow,
                node_map=node_map,
                runtime_event=runtime_event,
            )
            return self._workflow_node_started_event(
                workflow=workflow,
                run_identifier=run_identifier,
                node=node,
                checkpoint_payload=checkpoint_payload,
            )
        if event_type == "node_event":
            return self._translate_node_runtime_event(
                workflow=workflow,
                run_identifier=run_identifier,
                runtime_event=runtime_event,
                checkpoint_payload=checkpoint_payload,
                progress=progress,
            )
        if event_type == "node_retrying":
            node = self._require_runtime_node(
                workflow=workflow,
                node_map=node_map,
                runtime_event=runtime_event,
            )
            return self._workflow_node_retrying_event(
                workflow=workflow,
                run_identifier=run_identifier,
                runtime_event=runtime_event,
                node=node,
                checkpoint_payload=checkpoint_payload,
            )
        if event_type == "node_finished":
            node = self._require_runtime_node(
                workflow=workflow,
                node_map=node_map,
                runtime_event=runtime_event,
            )
            return self._workflow_node_finished_event(
                workflow=workflow,
                run_identifier=run_identifier,
                runtime_event=runtime_event,
                node=node,
                run_state=run_state,
                progress=progress,
                checkpoint_payload=checkpoint_payload,
            )
        if event_type == "completed":
            progress.status = "success"
            return self._workflow_run_finished_event(
                workflow=workflow,
                run_identifier=run_identifier,
                runtime_event=runtime_event,
                progress=progress,
                checkpoint_payload=checkpoint_payload,
            )
        if event_type in {"failed", "cancelled"}:
            reason = str(runtime_event.get("terminal_reason") or "workflow runtime error")
            raise ValueError(reason)
        raise ValueError(f"Unsupported orchestration runtime lifecycle '{event_type}'")

    @staticmethod
    def _workflow_run_started_event(
        *,
        workflow: Workflow,
        run_identifier: str,
        checkpoint_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "type": "workflow_run_started",
            "workflow_id": workflow.id,
            "run_id": run_identifier,
        }
        payload.update(checkpoint_payload)
        return payload

    @staticmethod
    def _workflow_node_started_event(
        *,
        workflow: Workflow,
        run_identifier: str,
        node: Any,
        checkpoint_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "type": "workflow_node_started",
            "workflow_id": workflow.id,
            "run_id": run_identifier,
            "node_id": node.id,
            "node_type": node.type,
        }
        payload.update(checkpoint_payload)
        return payload

    def _translate_node_runtime_event(
        self,
        *,
        workflow: Workflow,
        run_identifier: str,
        runtime_event: dict[str, Any],
        checkpoint_payload: dict[str, Any],
        progress: _ExecutionProgress,
    ) -> dict[str, Any]:
        node_id = str(runtime_event.get("node_id") or "")
        payload = self._runtime_payload(runtime_event)
        emitted_type = str(runtime_event.get("event_type") or "")

        if emitted_type == "text_delta":
            event = {
                "type": "text_delta",
                "workflow_id": workflow.id,
                "run_id": run_identifier,
                "node_id": node_id,
                "text": str(payload.get("text") or ""),
            }
        elif emitted_type == "workflow_condition_evaluated":
            event = {
                "type": "workflow_condition_evaluated",
                "workflow_id": workflow.id,
                "run_id": run_identifier,
                "node_id": node_id,
                "expression": payload.get("expression"),
                "result": payload.get("result"),
            }
        elif emitted_type == "workflow_output_reported":
            progress.output_text = str(payload.get("output") or "")
            event = {
                "type": "workflow_output_reported",
                "workflow_id": workflow.id,
                "run_id": run_identifier,
                "node_id": node_id,
                "output": progress.output_text,
            }
        elif emitted_type == "workflow_artifact_written":
            event = {
                "type": "workflow_artifact_written",
                "workflow_id": workflow.id,
                "run_id": run_identifier,
                "node_id": node_id,
                "file_path": payload.get("file_path"),
                "write_mode": payload.get("write_mode"),
                "written": payload.get("written"),
                "output_key": payload.get("output_key"),
                "content_hash": payload.get("content_hash"),
            }
        else:
            raise ValueError(f"Unsupported workflow runtime event '{emitted_type}'")

        event.update(checkpoint_payload)
        return event

    @staticmethod
    def _workflow_node_retrying_event(
        *,
        workflow: Workflow,
        run_identifier: str,
        runtime_event: dict[str, Any],
        node: Any,
        checkpoint_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "type": "workflow_node_retrying",
            "workflow_id": workflow.id,
            "run_id": run_identifier,
            "node_id": node.id,
            "node_type": node.type,
            "attempt": runtime_event.get("attempt"),
            "max_attempts": runtime_event.get("max_attempts"),
            "delay_ms": runtime_event.get("delay_ms"),
            "error": runtime_event.get("error"),
        }
        payload.update(checkpoint_payload)
        return payload

    def _workflow_node_finished_event(
        self,
        *,
        workflow: Workflow,
        run_identifier: str,
        runtime_event: dict[str, Any],
        node: Any,
        run_state: _WorkflowRunState,
        progress: _ExecutionProgress,
        checkpoint_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self._runtime_payload(runtime_event)
        finish_payload: dict[str, Any] = {
            "type": "workflow_node_finished",
            "workflow_id": workflow.id,
            "run_id": run_identifier,
            "node_id": node.id,
            "node_type": node.type,
        }

        if isinstance(node, LlmNode):
            output_key = str(payload.get("output_key") or f"node_{node.id}_output")
            node_output = str(payload.get("output") or "")
            usage = payload.get("usage")
            run_state.ctx[output_key] = node_output
            run_state.ctx["last_output"] = node_output
            progress.output_text = node_output
            finish_payload["output_key"] = output_key
            finish_payload["output"] = node_output
            if isinstance(usage, dict):
                finish_payload["usage"] = usage
        elif isinstance(node, ConditionNode):
            finish_payload["result"] = bool(payload.get("result"))
        elif isinstance(node, ArtifactNode):
            output_key = str(payload.get("output_key") or f"node_{node.id}_artifact")
            artifact_data = payload.get("artifact")
            if isinstance(artifact_data, dict):
                run_state.ctx[output_key] = artifact_data
                run_state.ctx["last_artifact"] = artifact_data
                artifact_content = payload.get("artifact_content")
                if isinstance(artifact_content, str):
                    run_state.ctx["last_output"] = artifact_content
                    progress.output_text = artifact_content
                finish_payload["output_key"] = output_key
                finish_payload["artifact"] = artifact_data
        elif isinstance(node, EndNode) and progress.output_text is None:
            progress.output_text = str(payload.get("output") or "")

        finish_payload.update(checkpoint_payload)
        return finish_payload

    @staticmethod
    def _workflow_run_finished_event(
        *,
        workflow: Workflow,
        run_identifier: str,
        runtime_event: dict[str, Any],
        progress: _ExecutionProgress,
        checkpoint_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = runtime_event.get("payload") or {}
        if isinstance(payload, dict):
            completed_output = payload.get("output")
            if isinstance(completed_output, str):
                progress.output_text = completed_output
        if progress.output_text is None:
            progress.output_text = ""
        event = {
            "type": "workflow_run_finished",
            "workflow_id": workflow.id,
            "run_id": run_identifier,
            "status": progress.status,
            "output": progress.output_text,
        }
        event.update(checkpoint_payload)
        return event

    async def execute_stream(
        self,
        workflow: Workflow,
        inputs: dict[str, Any] | None = None,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        context_type: str = "workflow",
        project_id: str | None = None,
        stream_mode: str = "default",
        artifact_target_path: str | None = None,
        write_mode: Literal["none", "create", "overwrite"] | None = None,
        resume_from_checkpoint_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute a workflow and stream runtime events."""
        run_identifier = run_id or str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        progress = _ExecutionProgress(normalized_inputs={}, ctx={})

        try:
            runtime = await self._resolve_runtime_config(
                session_id=session_id,
                context_type=context_type,
                project_id=project_id,
            )
            progress.normalized_inputs = self._validate_and_normalize_inputs(workflow, inputs or {})
            progress.ctx = {
                "run_id": run_identifier,
                "workflow_id": workflow.id,
                "started_at": started_at.isoformat(),
                "context_type": context_type,
                "project_id": project_id or "",
            }
            run_state = _WorkflowRunState(
                run_id=run_identifier,
                workflow=workflow,
                inputs=progress.normalized_inputs,
                ctx=progress.ctx,
                runtime=runtime,
                session_id=session_id,
                context_type=context_type,
                project_id=project_id,
                stream_mode=stream_mode,
                artifact_target_path=artifact_target_path,
                write_mode=write_mode,
            )
            run_spec = self._compile_workflow_run_spec(workflow, run_state)
            node_map = {node.id: node for node in workflow.nodes}
            run_context = self._build_run_context(
                run_id=run_identifier,
                workflow=workflow,
                context_type=context_type,
                project_id=project_id,
                resume_from_checkpoint_id=resume_from_checkpoint_id,
            )
            runtime_stream = self._runtime_stream(
                run_spec=run_spec,
                run_context=run_context,
                resume_from_checkpoint_id=resume_from_checkpoint_id,
            )

            async for runtime_event in runtime_stream:
                event = self._translate_runtime_event(
                    workflow=workflow,
                    run_identifier=run_identifier,
                    runtime_event=runtime_event,
                    node_map=node_map,
                    run_state=run_state,
                    progress=progress,
                )
                if event is not None:
                    yield event

        except Exception as exc:
            progress.error_message = str(exc)
            yield {
                "type": "stream_error",
                "workflow_id": workflow.id,
                "run_id": run_identifier,
                "error": progress.error_message,
            }
        finally:
            await self._append_run_record(
                workflow=workflow,
                run_identifier=run_identifier,
                started_at=started_at,
                progress=progress,
            )

    def _compile_workflow_run_spec(
        self,
        workflow: Workflow,
        run_state: _WorkflowRunState,
    ) -> RunSpec:
        node_specs: list[NodeSpec] = []
        edges: list[EdgeSpec] = []

        for node in workflow.nodes:
            if isinstance(node, StartNode):
                actor = ActorRef(
                    actor_id=node.id,
                    kind="workflow_start",
                    handler=cast(
                        Callable[[ActorExecutionContext], AsyncIterator[Any]],
                        lambda ctx, current=node: self._run_start_node(
                            execution_context=ctx,
                            node=current,
                        ),
                    ),
                )
                node_specs.append(
                    NodeSpec(
                        node_id=node.id,
                        actor=actor,
                        metadata={"node_type": node.type},
                    )
                )
                edges.append(EdgeSpec(source_id=node.id, target_id=node.next_id))
                continue

            if isinstance(node, LlmNode):
                timeout_ms = self._resolve_llm_timeout_ms(node)
                retry_count = self._resolve_llm_retry_count(node)
                retry_backoff_ms = self._resolve_llm_retry_backoff_ms(node)
                actor = ActorRef(
                    actor_id=node.id,
                    kind="workflow_llm",
                    handler=cast(
                        Callable[[ActorExecutionContext], AsyncIterator[Any]],
                        lambda ctx, current=node: self._run_llm_node(
                            execution_context=ctx,
                            node=current,
                            run_state=run_state,
                        ),
                    ),
                )
                node_specs.append(
                    NodeSpec(
                        node_id=node.id,
                        actor=actor,
                        timeout_ms=timeout_ms,
                        retry_policy=RetryPolicy(
                            max_retries=retry_count,
                            backoff_ms=retry_backoff_ms,
                            max_backoff_ms=self.max_llm_retry_backoff_ms,
                            retry_only_if_no_events=True,
                            is_retryable=self._is_retryable_llm_error,
                        ),
                        metadata={"node_type": node.type},
                    )
                )
                edges.append(EdgeSpec(source_id=node.id, target_id=node.next_id))
                continue

            if isinstance(node, ConditionNode):
                actor = ActorRef(
                    actor_id=node.id,
                    kind="workflow_condition",
                    handler=cast(
                        Callable[[ActorExecutionContext], AsyncIterator[Any]],
                        lambda ctx, current=node: self._run_condition_node(
                            execution_context=ctx,
                            node=current,
                            run_state=run_state,
                        ),
                    ),
                )
                node_specs.append(
                    NodeSpec(
                        node_id=node.id,
                        actor=actor,
                        metadata={"node_type": node.type},
                    )
                )
                edges.append(
                    EdgeSpec(source_id=node.id, target_id=node.true_next_id, branch="true")
                )
                edges.append(
                    EdgeSpec(source_id=node.id, target_id=node.false_next_id, branch="false")
                )
                continue

            if isinstance(node, ArtifactNode):
                actor = ActorRef(
                    actor_id=node.id,
                    kind="workflow_artifact",
                    handler=cast(
                        Callable[[ActorExecutionContext], AsyncIterator[Any]],
                        lambda ctx, current=node: self._run_artifact_node(
                            execution_context=ctx,
                            node=current,
                            run_state=run_state,
                        ),
                    ),
                )
                node_specs.append(
                    NodeSpec(
                        node_id=node.id,
                        actor=actor,
                        metadata={"node_type": node.type},
                    )
                )
                edges.append(EdgeSpec(source_id=node.id, target_id=node.next_id))
                continue

            if isinstance(node, EndNode):
                actor = ActorRef(
                    actor_id=node.id,
                    kind="workflow_end",
                    handler=cast(
                        Callable[[ActorExecutionContext], AsyncIterator[Any]],
                        lambda ctx, current=node: self._run_end_node(
                            execution_context=ctx,
                            node=current,
                            run_state=run_state,
                        ),
                    ),
                )
                node_specs.append(
                    NodeSpec(
                        node_id=node.id,
                        actor=actor,
                        metadata={"node_type": node.type},
                    )
                )
                continue

            raise ValueError(f"Unsupported node type '{node.type}'")

        return RunSpec(
            run_id=run_state.run_id,
            entry_node_id=workflow.entry_node_id,
            nodes=tuple(node_specs),
            edges=tuple(edges),
            metadata={
                "workflow_id": workflow.id,
                "context_type": run_state.context_type,
                "project_id": run_state.project_id or "",
            },
        )

    def _build_template_context(self, run_state: _WorkflowRunState) -> dict[str, Any]:
        return {"inputs": run_state.inputs, "ctx": run_state.ctx}

    async def _run_start_node(
        self,
        *,
        execution_context: ActorExecutionContext,
        node: StartNode,
    ) -> AsyncIterator[ActorEmit | ActorResult]:
        await execution_context.patch_context(
            namespace="workflow",
            payload={"status": "started"},
        )
        yield ActorResult(next_node_id=node.next_id)

    async def _run_llm_node(
        self,
        *,
        execution_context: ActorExecutionContext,
        node: LlmNode,
        run_state: _WorkflowRunState,
    ) -> AsyncIterator[ActorEmit | ActorResult]:
        template_context = self._build_template_context(run_state)
        prompt = self._render_template(node.prompt_template, template_context)
        request_params = self._build_llm_request_params(node=node, runtime=run_state.runtime)
        chunk_parts: list[str] = []
        usage: dict[str, Any] | None = None
        think_filter = ThinkTagStreamFilter() if run_state.stream_mode == "editor_rewrite" else None
        stream = self.llm_stream_fn(
            messages=[{"role": "user", "content": prompt}],
            session_id=f"workflow:{run_state.workflow.id}:{run_state.run_id}",
            **request_params,
        )
        try:
            async for chunk in stream:
                if isinstance(chunk, str):
                    visible_text = chunk
                    if think_filter is not None:
                        visible_text = think_filter.feed(chunk)
                        if not visible_text:
                            continue
                    chunk_parts.append(visible_text)
                    yield ActorEmit(event_type="text_delta", payload={"text": visible_text})
                    continue

                if isinstance(chunk, dict) and chunk.get("type") == "usage":
                    raw_usage = chunk.get("usage")
                    if isinstance(raw_usage, dict):
                        usage = raw_usage

            if think_filter is not None:
                tail = think_filter.flush()
                if tail:
                    chunk_parts.append(tail)
                    yield ActorEmit(event_type="text_delta", payload={"text": tail})
        finally:
            await self._close_async_iterator(stream)

        node_output = "".join(chunk_parts)
        output_key = node.output_key or f"node_{node.id}_output"
        run_state.ctx[output_key] = node_output
        run_state.ctx["last_output"] = node_output
        await execution_context.patch_context(
            namespace="workflow",
            payload={output_key: node_output, "last_output": node_output},
        )

        payload: dict[str, Any] = {
            "output_key": output_key,
            "output": node_output,
        }
        if usage:
            payload["usage"] = usage

        yield ActorResult(next_node_id=node.next_id, payload=payload)

    async def _run_condition_node(
        self,
        *,
        execution_context: ActorExecutionContext,
        node: ConditionNode,
        run_state: _WorkflowRunState,
    ) -> AsyncIterator[ActorEmit | ActorResult]:
        template_context = self._build_template_context(run_state)
        result = _ConditionParser(node.expression, template_context).parse()
        await execution_context.patch_context(
            namespace="workflow",
            payload={"last_condition_result": result},
        )
        yield ActorEmit(
            event_type="workflow_condition_evaluated",
            payload={
                "expression": node.expression,
                "result": result,
            },
        )
        yield ActorResult(
            branch="true" if result else "false",
            payload={"result": result},
        )

    async def _run_artifact_node(
        self,
        *,
        execution_context: ActorExecutionContext,
        node: ArtifactNode,
        run_state: _WorkflowRunState,
    ) -> AsyncIterator[ActorEmit | ActorResult]:
        if not run_state.project_id or run_state.context_type != "project":
            raise ValueError(
                "Artifact node requires project context (context_type='project' and project_id)"
            )

        template_context = self._build_template_context(run_state)
        artifact_file_path = (
            run_state.artifact_target_path or ""
        ).strip() or self._render_template(node.file_path_template, template_context).strip()
        artifact_file_path = self._validate_artifact_file_path(
            artifact_file_path,
            node_id=node.id,
        )

        node_write_mode = run_state.write_mode or node.write_mode
        if node_write_mode not in {"none", "create", "overwrite"}:
            raise ValueError(
                f"Unsupported write mode '{node_write_mode}' for artifact node '{node.id}'"
            )

        artifact_content = self._render_template(node.content_template, template_context)
        artifact_payload: dict[str, Any] = {
            "file_path": artifact_file_path,
            "write_mode": node_write_mode,
            "bytes": len(artifact_content.encode("utf-8")),
        }

        if node_write_mode == "none":
            artifact_payload["written"] = False
        else:
            if node_write_mode == "create":
                if await self._project_file_exists(run_state.project_id, artifact_file_path):
                    raise ValueError(f"Artifact path already exists: {artifact_file_path}")

            written_file = await self.project_service.write_file(
                run_state.project_id,
                artifact_file_path,
                artifact_content,
            )
            artifact_payload.update(
                {
                    "written": True,
                    "content_hash": written_file.content_hash,
                    "encoding": written_file.encoding,
                    "size": written_file.size,
                }
            )

        output_key = node.output_key or f"node_{node.id}_artifact"
        run_state.ctx[output_key] = artifact_payload
        run_state.ctx["last_artifact"] = artifact_payload
        run_state.ctx["last_output"] = artifact_content
        await execution_context.patch_context(
            namespace="workflow",
            payload={
                output_key: artifact_payload,
                "last_artifact": artifact_payload,
                "last_output": artifact_content,
            },
        )

        yield ActorEmit(
            event_type="workflow_artifact_written",
            payload={
                "file_path": artifact_file_path,
                "write_mode": node_write_mode,
                "written": artifact_payload.get("written", False),
                "output_key": output_key,
                "content_hash": artifact_payload.get("content_hash"),
            },
        )
        yield ActorResult(
            next_node_id=node.next_id,
            payload={
                "output_key": output_key,
                "artifact": artifact_payload,
                "artifact_content": artifact_content,
            },
        )

    async def _run_end_node(
        self,
        *,
        execution_context: ActorExecutionContext,
        node: EndNode,
        run_state: _WorkflowRunState,
    ) -> AsyncIterator[ActorEmit | ActorResult]:
        template_context = self._build_template_context(run_state)
        if node.result_template:
            output = self._render_template(node.result_template, template_context)
        else:
            output = str(run_state.ctx.get("last_output", "") or "")

        run_state.ctx["last_output"] = output
        await execution_context.patch_context(
            namespace="workflow",
            payload={"last_output": output},
        )
        yield ActorEmit(
            event_type="workflow_output_reported",
            payload={"output": output},
        )
        yield ActorResult(
            terminal_status="completed",
            terminal_reason="workflow completed",
            payload={"output": output},
        )

    def _build_llm_request_params(
        self,
        *,
        node: LlmNode,
        runtime: _ResolvedRuntimeConfig,
    ) -> dict[str, Any]:
        request_params: dict[str, Any] = {}
        model_id = node.model_id or runtime.model_id
        system_prompt = (
            node.system_prompt if node.system_prompt is not None else runtime.system_prompt
        )
        request_params["model_id"] = model_id
        request_params["system_prompt"] = system_prompt

        temperature = (
            node.temperature
            if node.temperature is not None
            else runtime.generation_params.get("temperature")
        )
        max_tokens = (
            node.max_tokens
            if node.max_tokens is not None
            else runtime.generation_params.get("max_tokens")
        )
        request_params["temperature"] = temperature
        request_params["max_tokens"] = max_tokens

        for key in ("top_p", "top_k", "frequency_penalty", "presence_penalty"):
            value = runtime.generation_params.get(key)
            if value is not None:
                request_params[key] = value

        return request_params

    def _resolve_llm_timeout_ms(self, node: LlmNode) -> int | None:
        if node.timeout_ms is None:
            return self.default_llm_timeout_ms
        return max(1, int(node.timeout_ms))

    def _resolve_llm_retry_count(self, node: LlmNode) -> int:
        if node.retry_count is None:
            return self.default_llm_retry_count
        return max(0, int(node.retry_count))

    def _resolve_llm_retry_backoff_ms(self, node: LlmNode) -> int:
        if node.retry_backoff_ms is None:
            return self.default_llm_retry_backoff_ms
        return max(0, int(node.retry_backoff_ms))

    def _is_retryable_llm_error(self, exc: Exception) -> bool:
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError)):
            return True
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return False

        message = str(exc).lower()
        retry_keywords = (
            "timeout",
            "timed out",
            "temporary",
            "temporarily",
            "try again",
            "rate limit",
            "429",
            "connection",
            "reset",
            "unavailable",
        )
        return any(keyword in message for keyword in retry_keywords)

    async def _close_async_iterator(self, stream: Any) -> None:
        aclose = getattr(stream, "aclose", None)
        if callable(aclose):
            with contextlib.suppress(Exception):
                close_result = aclose()
                if inspect.isawaitable(close_result):
                    await cast(Awaitable[Any], close_result)

    async def _resolve_runtime_config(
        self,
        *,
        session_id: str | None,
        context_type: str,
        project_id: str | None,
    ) -> _ResolvedRuntimeConfig:
        if not session_id or context_type not in {"chat", "project"}:
            return _ResolvedRuntimeConfig(model_id=None, system_prompt=None, generation_params={})

        session = await self.storage.get_session(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )

        assistant_id = session.get("assistant_id")
        model_id = session.get("model_id")
        system_prompt: str | None = None
        generation_params: dict[str, Any] = {}

        if isinstance(assistant_id, str) and assistant_id:
            assistant = await AssistantConfigService().get_assistant(assistant_id)
            if assistant:
                system_prompt = assistant.system_prompt
                model_id = assistant.model_id or model_id
                generation_params = self._extract_generation_params(assistant)

        param_overrides = session.get("param_overrides")
        if isinstance(param_overrides, dict):
            override_model_id = param_overrides.get("model_id")
            if isinstance(override_model_id, str) and override_model_id.strip():
                model_id = override_model_id.strip()
            for key in self._PARAM_KEYS:
                if key in param_overrides and param_overrides[key] is not None:
                    generation_params[key] = param_overrides[key]

        resolved_model_id = (
            model_id.strip() if isinstance(model_id, str) and model_id.strip() else None
        )
        return _ResolvedRuntimeConfig(
            model_id=resolved_model_id,
            system_prompt=system_prompt,
            generation_params=generation_params,
        )

    def _extract_generation_params(self, assistant_obj: Any) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for key in self._PARAM_KEYS:
            value = getattr(assistant_obj, key, None)
            if value is not None:
                params[key] = value
        return params

    def _validate_and_normalize_inputs(
        self,
        workflow: Workflow,
        raw_inputs: dict[str, Any],
    ) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        node_ids = {node.id for node in workflow.nodes}

        for input_def in workflow.input_schema:
            value = raw_inputs.get(input_def.key, input_def.default)
            if value is None:
                if input_def.required:
                    raise ValueError(f"Missing required input '{input_def.key}'")
                continue

            if input_def.type == "string":
                if not isinstance(value, str):
                    raise ValueError(f"Input '{input_def.key}' must be a string")
                if input_def.max_length is not None and len(value) > input_def.max_length:
                    raise ValueError(
                        f"Input '{input_def.key}' exceeds max length ({input_def.max_length})"
                    )
                if input_def.pattern:
                    try:
                        if re.fullmatch(input_def.pattern, value) is None:
                            raise ValueError(f"Input '{input_def.key}' format is invalid")
                    except re.error as exc:
                        raise ValueError(
                            f"Input '{input_def.key}' has invalid pattern config: {exc}"
                        ) from exc
                normalized[input_def.key] = value
                continue

            if input_def.type == "number":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"Input '{input_def.key}' must be a number")
                normalized[input_def.key] = value
                continue

            if input_def.type == "boolean":
                if not isinstance(value, bool):
                    raise ValueError(f"Input '{input_def.key}' must be a boolean")
                normalized[input_def.key] = value
                continue

            if input_def.type == "node":
                if not isinstance(value, str):
                    raise ValueError(f"Input '{input_def.key}' must be a node id string")
                if _NODE_ID_PATTERN.fullmatch(value) is None:
                    raise ValueError(f"Input '{input_def.key}' must match node id pattern")
                if value not in node_ids:
                    raise ValueError(
                        f"Input '{input_def.key}' references unknown node id '{value}'"
                    )
                normalized[input_def.key] = value
                continue

            raise ValueError(f"Unsupported input type '{input_def.type}'")

        for key, value in raw_inputs.items():
            if key not in normalized:
                normalized[key] = value

        return normalized

    def _render_template(self, template: str, context: dict[str, Any]) -> str:
        def repl(match: re.Match[str]) -> str:
            path = match.group(1)
            try:
                value = _resolve_context_path(context, path)
            except ValueError:
                return ""
            if value is None:
                return ""
            if isinstance(value, (dict, list)):
                return str(value)
            return str(value)

        return _TEMPLATE_PATTERN.sub(repl, template)

    async def _project_file_exists(self, project_id: str, relative_path: str) -> bool:
        try:
            await self.project_service.read_file(project_id, relative_path)
            return True
        except ValueError as exc:
            message = str(exc).lower()
            if "path does not exist" in message or "file not found" in message:
                return False
            raise

    def _validate_artifact_file_path(self, raw_path: str, *, node_id: str) -> str:
        normalized_path = raw_path.replace("\\", "/").strip()
        if not normalized_path:
            raise ValueError(f"Artifact node '{node_id}' produced empty file path")
        if normalized_path.startswith("/") or _WINDOWS_DRIVE_PREFIX.match(normalized_path):
            raise ValueError(
                f"Artifact node '{node_id}' path must be project-relative: {normalized_path}"
            )
        if _INVALID_ARTIFACT_PATH_CHAR_RE.search(normalized_path):
            raise ValueError(
                f"Artifact node '{node_id}' produced invalid path characters. "
                "Check file_path_template or inputs (for example, chapter_id should be short text)."
            )
        if len(normalized_path) > 240:
            raise ValueError(
                f"Artifact node '{node_id}' produced an overlong path ({len(normalized_path)} chars)"
            )

        parts = [part for part in normalized_path.split("/") if part]
        if not parts:
            raise ValueError(f"Artifact node '{node_id}' produced empty file path")
        for part in parts:
            if part in {".", ".."}:
                raise ValueError(f"Artifact node '{node_id}' produced unsafe path segment '{part}'")
            if part.endswith(" ") or part.endswith("."):
                raise ValueError(
                    f"Artifact node '{node_id}' path segment cannot end with dot or space: '{part}'"
                )

        return "/".join(parts)
