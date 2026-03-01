"""Workflow runtime execution service."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

from src.agents.simple_llm import call_llm_stream

from ..models.workflow import ConditionNode, EndNode, LlmNode, StartNode, Workflow, WorkflowRunRecord
from .workflow_run_history_service import WorkflowRunHistoryService


_TEMPLATE_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*}}")


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str


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

    def __init__(
        self,
        *,
        history_service: Optional[WorkflowRunHistoryService] = None,
        llm_stream_fn: Optional[
            Callable[..., AsyncIterator[Union[str, Dict[str, Any]]]]
        ] = None,
        max_steps: int = 100,
    ):
        self.history_service = history_service or WorkflowRunHistoryService()
        self.llm_stream_fn = llm_stream_fn or call_llm_stream
        self.max_steps = max(1, int(max_steps))

    async def execute_stream(
        self,
        workflow: Workflow,
        inputs: Optional[Dict[str, Any]] = None,
        *,
        run_id: Optional[str] = None,
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
            normalized_inputs = self._validate_and_normalize_inputs(workflow, inputs or {})
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
                    chunk_parts: List[str] = []
                    usage: Optional[Dict[str, Any]] = None

                    async for chunk in self.llm_stream_fn(
                        messages=[{"role": "user", "content": prompt}],
                        session_id=f"workflow:{workflow.id}:{run_identifier}",
                        model_id=node.model_id,
                        system_prompt=node.system_prompt,
                        temperature=node.temperature,
                        max_tokens=node.max_tokens,
                    ):
                        if isinstance(chunk, str):
                            chunk_parts.append(chunk)
                            yield {
                                "type": "text_delta",
                                "workflow_id": workflow.id,
                                "run_id": run_identifier,
                                "node_id": node.id,
                                "text": chunk,
                            }
                            continue

                        if isinstance(chunk, dict) and chunk.get("type") == "usage":
                            raw_usage = chunk.get("usage")
                            if isinstance(raw_usage, dict):
                                usage = raw_usage

                    node_output = "".join(chunk_parts)
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

    def _validate_and_normalize_inputs(
        self,
        workflow: Workflow,
        raw_inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}

        for input_def in workflow.input_schema:
            value = raw_inputs.get(input_def.key, input_def.default)
            if value is None:
                if input_def.required:
                    raise ValueError(f"Missing required input '{input_def.key}'")
                continue

            if input_def.type == "string":
                if not isinstance(value, str):
                    raise ValueError(f"Input '{input_def.key}' must be a string")
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
