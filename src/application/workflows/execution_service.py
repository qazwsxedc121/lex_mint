"""Workflow runtime execution service."""

from __future__ import annotations

import asyncio
import contextlib
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Dict, List, Literal, Optional, Union

from src.llm_runtime import call_llm_stream
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
from src.llm_runtime.think_tag_filter import ThinkTagStreamFilter
from src.application.workflows.run_history_service import WorkflowRunHistoryService


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
    model_id: Optional[str]
    system_prompt: Optional[str]
    generation_params: Dict[str, Any]


class _NodeAttemptTimeoutError(Exception):
    """Raised when one LLM attempt exceeds configured timeout."""


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

    def __init__(self, expression: str, context: Dict[str, Any]):
        self.tokens = self._tokenize(expression)
        self.pos = 0
        self.context = context

    def _tokenize(self, expression: str) -> List[_Token]:
        tokens: List[_Token] = []
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

    def _peek(self) -> Optional[_Token]:
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def _consume(self, expected_kind: Optional[str] = None) -> _Token:
        token = self._peek()
        if token is None:
            raise ValueError("Unexpected end of expression")
        if expected_kind is not None and token.kind != expected_kind:
            raise ValueError(f"Expected {expected_kind}, got {token.kind}")
        self.pos += 1
        return token

    def parse(self) -> bool:
        value = self._parse_or_expr()
        if self._peek() is not None:
            raise ValueError(f"Unexpected token '{self._peek().value}'")
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
            return left == right
        if op == "!=":
            return left != right
        if op == ">":
            return left > right
        if op == "<":
            return left < right
        if op == ">=":
            return left >= right
        if op == "<=":
            return left <= right
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


def _resolve_context_path(context: Dict[str, Any], path: str) -> Any:
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
        history_service: Optional[WorkflowRunHistoryService] = None,
        llm_stream_fn: Optional[
            Callable[..., AsyncIterator[Union[str, Dict[str, Any]]]]
        ] = None,
        storage: Optional[ConversationStorage] = None,
        project_service: Optional[ProjectService] = None,
        max_steps: int = 100,
        default_llm_timeout_ms: Optional[int] = 180000,
        default_llm_retry_count: int = 1,
        default_llm_retry_backoff_ms: int = 300,
        max_llm_retry_backoff_ms: int = 5000,
    ):
        self.history_service = history_service or WorkflowRunHistoryService()
        self.llm_stream_fn = llm_stream_fn or call_llm_stream
        self.storage = storage or create_storage_with_project_resolver(settings.conversations_dir)
        self.project_service = project_service or ProjectService()
        self.max_steps = max(1, int(max_steps))
        self.default_llm_timeout_ms = (
            None
            if default_llm_timeout_ms is None
            else max(1, int(default_llm_timeout_ms))
        )
        self.default_llm_retry_count = max(0, int(default_llm_retry_count))
        self.default_llm_retry_backoff_ms = max(0, int(default_llm_retry_backoff_ms))
        self.max_llm_retry_backoff_ms = max(0, int(max_llm_retry_backoff_ms))

    async def execute_stream(
        self,
        workflow: Workflow,
        inputs: Optional[Dict[str, Any]] = None,
        *,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context_type: str = "workflow",
        project_id: Optional[str] = None,
        stream_mode: str = "default",
        artifact_target_path: Optional[str] = None,
        write_mode: Optional[Literal["none", "create", "overwrite"]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute a workflow and stream runtime events."""
        run_identifier = run_id or str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        normalized_inputs: Dict[str, Any] = {}
        ctx: Dict[str, Any] = {}
        output_text: Optional[str] = None
        status: str = "error"
        error_message: Optional[str] = None

        try:
            runtime = await self._resolve_runtime_config(
                session_id=session_id,
                context_type=context_type,
                project_id=project_id,
            )
            normalized_inputs = self._validate_and_normalize_inputs(workflow, inputs or {})
            ctx = {
                "run_id": run_identifier,
                "workflow_id": workflow.id,
                "started_at": started_at.isoformat(),
                "context_type": context_type,
                "project_id": project_id or "",
            }
            node_map = {node.id: node for node in workflow.nodes}
            current_id = workflow.entry_node_id
            step_count = 0

            yield {
                "type": "workflow_run_started",
                "workflow_id": workflow.id,
                "run_id": run_identifier,
            }

            while True:
                if step_count >= self.max_steps:
                    raise ValueError(
                        f"Workflow exceeded max steps ({self.max_steps}), possible loop detected"
                    )
                step_count += 1

                node = node_map[current_id]
                yield {
                    "type": "workflow_node_started",
                    "workflow_id": workflow.id,
                    "run_id": run_identifier,
                    "node_id": node.id,
                    "node_type": node.type,
                }

                template_context = {"inputs": normalized_inputs, "ctx": ctx}

                if isinstance(node, StartNode):
                    yield {
                        "type": "workflow_node_finished",
                        "workflow_id": workflow.id,
                        "run_id": run_identifier,
                        "node_id": node.id,
                        "node_type": node.type,
                    }
                    current_id = node.next_id
                    continue

                if isinstance(node, LlmNode):
                    prompt = self._render_template(node.prompt_template, template_context)
                    request_params = self._build_llm_request_params(node=node, runtime=runtime)
                    timeout_ms = self._resolve_llm_timeout_ms(node)
                    max_retries = self._resolve_llm_retry_count(node)
                    backoff_ms = self._resolve_llm_retry_backoff_ms(node)
                    max_attempts = max_retries + 1
                    usage: Optional[Dict[str, Any]] = None
                    node_output = ""
                    for attempt in range(1, max_attempts + 1):
                        chunk_parts: List[str] = []
                        attempt_usage: Optional[Dict[str, Any]] = None
                        think_filter = (
                            ThinkTagStreamFilter() if stream_mode == "editor_rewrite" else None
                        )
                        attempt_emitted_text = False
                        stream = self.llm_stream_fn(
                            messages=[{"role": "user", "content": prompt}],
                            session_id=f"workflow:{workflow.id}:{run_identifier}",
                            **request_params,
                        )
                        deadline = (
                            time.monotonic() + (timeout_ms / 1000.0)
                            if timeout_ms is not None
                            else None
                        )
                        try:
                            iterator = stream.__aiter__()
                            while True:
                                if deadline is not None:
                                    remaining = deadline - time.monotonic()
                                    if remaining <= 0:
                                        raise _NodeAttemptTimeoutError(
                                            f"LLM node '{node.id}' timed out after {timeout_ms} ms"
                                        )
                                else:
                                    remaining = None
                                try:
                                    if remaining is None:
                                        chunk = await iterator.__anext__()
                                    else:
                                        chunk = await asyncio.wait_for(iterator.__anext__(), timeout=remaining)
                                except asyncio.TimeoutError as exc:
                                    if str(exc):
                                        raise
                                    raise _NodeAttemptTimeoutError(
                                        f"LLM node '{node.id}' timed out after {timeout_ms} ms"
                                    ) from exc
                                except StopAsyncIteration:
                                    break

                                if isinstance(chunk, str):
                                    visible_text = chunk
                                    if think_filter is not None:
                                        visible_text = think_filter.feed(chunk)
                                        if not visible_text:
                                            continue
                                    chunk_parts.append(visible_text)
                                    attempt_emitted_text = True
                                    yield {
                                        "type": "text_delta",
                                        "workflow_id": workflow.id,
                                        "run_id": run_identifier,
                                        "node_id": node.id,
                                        "text": visible_text,
                                    }
                                    continue

                                if isinstance(chunk, dict) and chunk.get("type") == "usage":
                                    raw_usage = chunk.get("usage")
                                    if isinstance(raw_usage, dict):
                                        attempt_usage = raw_usage

                            if think_filter is not None:
                                tail = think_filter.flush()
                                if tail:
                                    chunk_parts.append(tail)
                                    attempt_emitted_text = True
                                    yield {
                                        "type": "text_delta",
                                        "workflow_id": workflow.id,
                                        "run_id": run_identifier,
                                        "node_id": node.id,
                                        "text": tail,
                                    }

                            node_output = "".join(chunk_parts)
                            usage = attempt_usage
                            break
                        except _NodeAttemptTimeoutError as timeout_error:
                            should_retry = (
                                attempt < max_attempts
                                and not attempt_emitted_text
                                and self._is_retryable_llm_error(timeout_error)
                            )
                            if not should_retry:
                                raise timeout_error

                            delay_ms = self._compute_backoff_delay_ms(
                                base_delay_ms=backoff_ms,
                                retry_index=attempt,
                            )
                            yield {
                                "type": "workflow_node_retrying",
                                "workflow_id": workflow.id,
                                "run_id": run_identifier,
                                "node_id": node.id,
                                "node_type": node.type,
                                "attempt": attempt + 1,
                                "max_attempts": max_attempts,
                                "delay_ms": delay_ms,
                                "error": str(timeout_error),
                            }
                            if delay_ms > 0:
                                await asyncio.sleep(delay_ms / 1000)
                            continue
                        except Exception as exc:
                            should_retry = (
                                attempt < max_attempts
                                and not attempt_emitted_text
                                and self._is_retryable_llm_error(exc)
                            )
                            if not should_retry:
                                raise

                            delay_ms = self._compute_backoff_delay_ms(
                                base_delay_ms=backoff_ms,
                                retry_index=attempt,
                            )
                            yield {
                                "type": "workflow_node_retrying",
                                "workflow_id": workflow.id,
                                "run_id": run_identifier,
                                "node_id": node.id,
                                "node_type": node.type,
                                "attempt": attempt + 1,
                                "max_attempts": max_attempts,
                                "delay_ms": delay_ms,
                                "error": str(exc),
                            }
                            if delay_ms > 0:
                                await asyncio.sleep(delay_ms / 1000)
                            continue
                        finally:
                            await self._close_async_iterator(stream)

                    else:
                        raise ValueError(
                            f"LLM node '{node.id}' failed after {max_attempts} attempts"
                        )

                    output_key = node.output_key or f"node_{node.id}_output"
                    ctx[output_key] = node_output
                    ctx["last_output"] = node_output
                    output_text = node_output

                    finish_payload: Dict[str, Any] = {
                        "type": "workflow_node_finished",
                        "workflow_id": workflow.id,
                        "run_id": run_identifier,
                        "node_id": node.id,
                        "node_type": node.type,
                        "output_key": output_key,
                        "output": node_output,
                    }
                    if usage:
                        finish_payload["usage"] = usage
                    yield finish_payload
                    current_id = node.next_id
                    continue

                if isinstance(node, ConditionNode):
                    result = _ConditionParser(node.expression, template_context).parse()
                    yield {
                        "type": "workflow_condition_evaluated",
                        "workflow_id": workflow.id,
                        "run_id": run_identifier,
                        "node_id": node.id,
                        "expression": node.expression,
                        "result": result,
                    }
                    yield {
                        "type": "workflow_node_finished",
                        "workflow_id": workflow.id,
                        "run_id": run_identifier,
                        "node_id": node.id,
                        "node_type": node.type,
                        "result": result,
                    }
                    current_id = node.true_next_id if result else node.false_next_id
                    continue

                if isinstance(node, EndNode):
                    if node.result_template:
                        output_text = self._render_template(node.result_template, template_context)
                    elif output_text is None:
                        output_text = ""

                    yield {
                        "type": "workflow_output_reported",
                        "workflow_id": workflow.id,
                        "run_id": run_identifier,
                        "node_id": node.id,
                        "output": output_text,
                    }
                    yield {
                        "type": "workflow_node_finished",
                        "workflow_id": workflow.id,
                        "run_id": run_identifier,
                        "node_id": node.id,
                        "node_type": node.type,
                    }
                    status = "success"
                    yield {
                        "type": "workflow_run_finished",
                        "workflow_id": workflow.id,
                        "run_id": run_identifier,
                        "status": status,
                        "output": output_text,
                    }
                    break

                if isinstance(node, ArtifactNode):
                    if not project_id or context_type != "project":
                        raise ValueError(
                            "Artifact node requires project context (context_type='project' and project_id)"
                        )

                    artifact_file_path = (
                        (artifact_target_path or "").strip()
                        or self._render_template(node.file_path_template, template_context).strip()
                    )
                    artifact_file_path = self._validate_artifact_file_path(
                        artifact_file_path,
                        node_id=node.id,
                    )

                    node_write_mode = write_mode or node.write_mode
                    if node_write_mode not in {"none", "create", "overwrite"}:
                        raise ValueError(
                            f"Unsupported write mode '{node_write_mode}' for artifact node '{node.id}'"
                        )

                    artifact_content = self._render_template(node.content_template, template_context)
                    artifact_payload: Dict[str, Any] = {
                        "file_path": artifact_file_path,
                        "write_mode": node_write_mode,
                        "bytes": len(artifact_content.encode("utf-8")),
                    }

                    if node_write_mode == "none":
                        artifact_payload["written"] = False
                    else:
                        if node_write_mode == "create":
                            if await self._project_file_exists(project_id, artifact_file_path):
                                raise ValueError(
                                    f"Artifact path already exists: {artifact_file_path}"
                                )

                        written_file = await self.project_service.write_file(
                            project_id,
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
                    ctx[output_key] = artifact_payload
                    ctx["last_artifact"] = artifact_payload
                    ctx["last_output"] = artifact_content
                    output_text = artifact_content

                    yield {
                        "type": "workflow_artifact_written",
                        "workflow_id": workflow.id,
                        "run_id": run_identifier,
                        "node_id": node.id,
                        "file_path": artifact_file_path,
                        "write_mode": node_write_mode,
                        "written": artifact_payload.get("written", False),
                        "output_key": output_key,
                        "content_hash": artifact_payload.get("content_hash"),
                    }
                    yield {
                        "type": "workflow_node_finished",
                        "workflow_id": workflow.id,
                        "run_id": run_identifier,
                        "node_id": node.id,
                        "node_type": node.type,
                        "output_key": output_key,
                        "artifact": artifact_payload,
                    }
                    current_id = node.next_id
                    continue

                raise ValueError(f"Unsupported node type '{node.type}'")

        except Exception as exc:
            error_message = str(exc)
            yield {
                "type": "stream_error",
                "workflow_id": workflow.id,
                "run_id": run_identifier,
                "error": error_message,
            }
        finally:
            finished_at = datetime.now(timezone.utc)
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            record = WorkflowRunRecord(
                run_id=run_identifier,
                workflow_id=workflow.id,
                status="success" if status == "success" else "error",
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                inputs=normalized_inputs,
                output=output_text,
                node_outputs=ctx,
                error=error_message,
            )
            await self.history_service.append_run(record)

    def _build_llm_request_params(
        self,
        *,
        node: LlmNode,
        runtime: _ResolvedRuntimeConfig,
    ) -> Dict[str, Any]:
        request_params: Dict[str, Any] = {}
        model_id = node.model_id or runtime.model_id
        system_prompt = (
            node.system_prompt
            if node.system_prompt is not None
            else runtime.system_prompt
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

    def _resolve_llm_timeout_ms(self, node: LlmNode) -> Optional[int]:
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

    def _compute_backoff_delay_ms(self, *, base_delay_ms: int, retry_index: int) -> int:
        if base_delay_ms <= 0:
            return 0
        # retry_index starts from 1 (first retry)
        delay = int(base_delay_ms * (2 ** max(0, retry_index - 1)))
        return min(delay, self.max_llm_retry_backoff_ms)

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
                await aclose()

    async def _resolve_runtime_config(
        self,
        *,
        session_id: Optional[str],
        context_type: str,
        project_id: Optional[str],
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
        system_prompt: Optional[str] = None
        generation_params: Dict[str, Any] = {}

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

        resolved_model_id = model_id.strip() if isinstance(model_id, str) and model_id.strip() else None
        return _ResolvedRuntimeConfig(
            model_id=resolved_model_id,
            system_prompt=system_prompt,
            generation_params=generation_params,
        )

    def _extract_generation_params(self, assistant_obj: Any) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for key in self._PARAM_KEYS:
            value = getattr(assistant_obj, key, None)
            if value is not None:
                params[key] = value
        return params

    def _validate_and_normalize_inputs(
        self,
        workflow: Workflow,
        raw_inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
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
                            raise ValueError(
                                f"Input '{input_def.key}' format is invalid"
                            )
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

    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
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
                raise ValueError(
                    f"Artifact node '{node_id}' produced unsafe path segment '{part}'"
                )
            if part.endswith(" ") or part.endswith("."):
                raise ValueError(
                    f"Artifact node '{node_id}' path segment cannot end with dot or space: '{part}'"
                )

        return "/".join(parts)
