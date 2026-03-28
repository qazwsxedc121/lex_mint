"""Workflow configuration and run history models."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_KEY_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"
_TEMPLATE_VAR_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*}}")
_CONDITION_STRING_PATTERN = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
_CONDITION_IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_.]*\b")
_CONDITION_RESERVED_WORDS = {"and", "or", "not", "true", "false"}


class WorkflowInputDef(BaseModel):
    """Input schema entry for one workflow parameter."""

    key: str = Field(..., pattern=_KEY_PATTERN)
    type: Literal["string", "number", "boolean", "node"] = "string"
    required: bool = False
    default: str | int | float | bool | None = None
    description: str | None = None
    allow_file_insert: bool | None = None
    max_length: int | None = Field(default=None, ge=1, le=200000)
    pattern: str | None = None

    @model_validator(mode="after")
    def validate_default_type(self) -> WorkflowInputDef:
        """Ensure default values match configured input type."""
        if self.default is None:
            return self

        if self.type == "string" and not isinstance(self.default, str):
            raise ValueError(f"Input '{self.key}' default must be a string")

        if self.type == "number" and (
            isinstance(self.default, bool) or not isinstance(self.default, (int, float))
        ):
            raise ValueError(f"Input '{self.key}' default must be a number")

        if self.type == "boolean" and not isinstance(self.default, bool):
            raise ValueError(f"Input '{self.key}' default must be a boolean")

        if self.type == "node":
            if not isinstance(self.default, str):
                raise ValueError(f"Input '{self.key}' default must be a node id string")
            if re.fullmatch(_KEY_PATTERN, self.default) is None:
                raise ValueError(f"Input '{self.key}' default must match node id pattern")

        if self.type != "string":
            if self.max_length is not None:
                raise ValueError(f"Input '{self.key}' max_length is only valid for string inputs")
            if self.pattern is not None:
                raise ValueError(f"Input '{self.key}' pattern is only valid for string inputs")

        if self.type == "string" and isinstance(self.default, str):
            if self.max_length is not None and len(self.default) > self.max_length:
                raise ValueError(
                    f"Input '{self.key}' default exceeds max_length ({self.max_length})"
                )
            if self.pattern:
                try:
                    compiled = re.compile(self.pattern)
                except re.error as exc:
                    raise ValueError(f"Input '{self.key}' has invalid pattern: {exc}") from exc
                if not compiled.fullmatch(self.default):
                    raise ValueError(f"Input '{self.key}' default does not match pattern")

        return self


class StartNode(BaseModel):
    """Workflow start node."""

    id: str = Field(..., pattern=_KEY_PATTERN)
    type: Literal["start"]
    next_id: str = Field(..., pattern=_KEY_PATTERN)


class LlmNode(BaseModel):
    """Workflow LLM node."""

    id: str = Field(..., pattern=_KEY_PATTERN)
    type: Literal["llm"]
    prompt_template: str
    model_id: str | None = None
    system_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    timeout_ms: int | None = Field(default=None, ge=1, le=900000)
    retry_count: int | None = Field(default=None, ge=0, le=10)
    retry_backoff_ms: int | None = Field(default=None, ge=0, le=120000)
    output_key: str | None = Field(default=None, pattern=_KEY_PATTERN)
    next_id: str = Field(..., pattern=_KEY_PATTERN)

    @field_validator("prompt_template")
    @classmethod
    def validate_prompt_template(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("LLM node prompt_template cannot be empty")
        return stripped


class ConditionNode(BaseModel):
    """Workflow condition node."""

    id: str = Field(..., pattern=_KEY_PATTERN)
    type: Literal["condition"]
    expression: str
    true_next_id: str = Field(..., pattern=_KEY_PATTERN)
    false_next_id: str = Field(..., pattern=_KEY_PATTERN)

    @field_validator("expression")
    @classmethod
    def validate_expression(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Condition node expression cannot be empty")
        return stripped


class EndNode(BaseModel):
    """Workflow end node."""

    id: str = Field(..., pattern=_KEY_PATTERN)
    type: Literal["end"]
    result_template: str | None = None


class ArtifactNode(BaseModel):
    """Workflow artifact node (write rendered content to a project file)."""

    id: str = Field(..., pattern=_KEY_PATTERN)
    type: Literal["artifact"]
    file_path_template: str
    content_template: str = "{{ctx.last_output}}"
    write_mode: Literal["create", "overwrite"] = "overwrite"
    output_key: str | None = Field(default=None, pattern=_KEY_PATTERN)
    next_id: str = Field(..., pattern=_KEY_PATTERN)

    @field_validator("file_path_template")
    @classmethod
    def validate_file_path_template(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Artifact node file_path_template cannot be empty")
        return stripped

    @field_validator("content_template")
    @classmethod
    def validate_content_template(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Artifact node content_template cannot be empty")
        return stripped


WorkflowNode = Annotated[
    StartNode | LlmNode | ConditionNode | ArtifactNode | EndNode,
    Field(discriminator="type"),
]


class WorkflowBase(BaseModel):
    """Shared workflow fields."""

    name: str
    description: str | None = None
    enabled: bool = True
    scenario: Literal["general", "editor_rewrite", "project_pipeline"] = "general"
    is_system: bool = False
    template_version: int | None = Field(default=None, ge=1)
    input_schema: list[WorkflowInputDef] = Field(default_factory=list)
    entry_node_id: str = Field(..., pattern=_KEY_PATTERN)
    nodes: list[WorkflowNode] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Workflow name cannot be empty")
        return stripped

    @field_validator("input_schema")
    @classmethod
    def validate_unique_input_keys(cls, value: list[WorkflowInputDef]) -> list[WorkflowInputDef]:
        seen = set()
        for item in value:
            key_lower = item.key.lower()
            if key_lower in seen:
                raise ValueError(f"Duplicate input key '{item.key}'")
            seen.add(key_lower)
        return value

    @model_validator(mode="after")
    def validate_graph(self) -> WorkflowBase:
        if not self.nodes:
            raise ValueError("Workflow must include at least one node")

        node_ids: set[str] = set()
        input_keys = {item.key for item in self.input_schema}
        node_by_id: dict[str, WorkflowNode] = {}
        adjacency: dict[str, list[str]] = {}
        has_start = False
        has_end = False

        for node in self.nodes:
            if node.id in node_ids:
                raise ValueError(f"Duplicate node id '{node.id}'")
            node_ids.add(node.id)
            node_by_id[node.id] = node
            if node.type == "start":
                has_start = True
            if node.type == "end":
                has_end = True

        if self.entry_node_id not in node_ids:
            raise ValueError(f"entry_node_id '{self.entry_node_id}' does not exist")

        if not has_start:
            raise ValueError("Workflow must include at least one start node")
        if not has_end:
            raise ValueError("Workflow must include at least one end node")

        entry_node = node_by_id[self.entry_node_id]
        if not isinstance(entry_node, StartNode):
            raise ValueError(f"entry_node_id '{self.entry_node_id}' must reference a start node")

        for node in self.nodes:
            targets: list[str] = []
            if isinstance(node, StartNode):
                targets = [node.next_id]
            elif isinstance(node, LlmNode):
                targets = [node.next_id]
            elif isinstance(node, ConditionNode):
                targets = [node.true_next_id, node.false_next_id]
            elif isinstance(node, ArtifactNode):
                targets = [node.next_id]
            adjacency[node.id] = targets

            for target in targets:
                if target not in node_ids:
                    raise ValueError(f"Node '{node.id}' references missing next node '{target}'")

        self._validate_reachability(adjacency, node_ids)
        self._validate_acyclic(adjacency, node_ids)
        self._validate_template_variables(input_keys=input_keys)
        self._validate_condition_variables(input_keys=input_keys)

        return self

    def _validate_reachability(self, adjacency: dict[str, list[str]], node_ids: set[str]) -> None:
        reachable: set[str] = set()
        stack = [self.entry_node_id]

        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            for target in adjacency.get(current, []):
                if target not in reachable:
                    stack.append(target)

        unreachable = sorted(node_ids - reachable)
        if unreachable:
            raise ValueError(
                "Workflow contains unreachable nodes from entry node: " + ", ".join(unreachable)
            )

        if not any(isinstance(node, EndNode) and node.id in reachable for node in self.nodes):
            raise ValueError("Workflow entry path must reach at least one end node")

    def _validate_acyclic(self, adjacency: dict[str, list[str]], node_ids: set[str]) -> None:
        in_degree: dict[str, int] = dict.fromkeys(node_ids, 0)
        for targets in adjacency.values():
            for target in targets:
                in_degree[target] += 1

        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        visited = 0
        index = 0

        while index < len(queue):
            current = queue[index]
            index += 1
            visited += 1
            for target in adjacency.get(current, []):
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)

        if visited != len(node_ids):
            raise ValueError("Workflow contains a cycle; looping graphs are not supported")

    def _validate_template_variables(self, *, input_keys: set[str]) -> None:
        for node in self.nodes:
            template_fields: list[tuple[str, str | None]] = []

            if isinstance(node, LlmNode):
                template_fields.append(("prompt_template", node.prompt_template))
                template_fields.append(("system_prompt", node.system_prompt))
            elif isinstance(node, ArtifactNode):
                template_fields.append(("file_path_template", node.file_path_template))
                template_fields.append(("content_template", node.content_template))
            elif isinstance(node, EndNode):
                template_fields.append(("result_template", node.result_template))

            for field_name, template_value in template_fields:
                if not template_value:
                    continue
                for match in _TEMPLATE_VAR_PATTERN.finditer(template_value):
                    path = match.group(1)
                    self._validate_context_reference(
                        path=path,
                        input_keys=input_keys,
                        source=f"node '{node.id}' {field_name}",
                    )

    def _validate_condition_variables(self, *, input_keys: set[str]) -> None:
        for node in self.nodes:
            if not isinstance(node, ConditionNode):
                continue

            expression = _CONDITION_STRING_PATTERN.sub(" ", node.expression)
            for identifier in _CONDITION_IDENTIFIER_PATTERN.findall(expression):
                if identifier.lower() in _CONDITION_RESERVED_WORDS:
                    continue
                self._validate_context_reference(
                    path=identifier,
                    input_keys=input_keys,
                    source=f"node '{node.id}' expression",
                )

    def _validate_context_reference(
        self,
        *,
        path: str,
        input_keys: set[str],
        source: str,
    ) -> None:
        if path == "inputs":
            raise ValueError(f"{source} references 'inputs' directly; use inputs.<key>")

        if path == "ctx" or path.startswith("ctx."):
            return

        if not path.startswith("inputs."):
            raise ValueError(f"{source} uses unsupported reference '{path}'. Use inputs.* or ctx.*")

        input_key = path.split(".", maxsplit=2)[1].strip()
        if not input_key:
            raise ValueError(f"{source} contains invalid input reference '{path}'")
        if input_key not in input_keys:
            raise ValueError(f"{source} references unknown input '{input_key}' (from '{path}')")


class Workflow(WorkflowBase):
    """Persisted workflow."""

    id: str = Field(..., pattern=_KEY_PATTERN)
    created_at: datetime
    updated_at: datetime


class WorkflowsConfig(BaseModel):
    """Workflow config file schema."""

    workflows: list[Workflow] = Field(default_factory=list)


class WorkflowCreate(WorkflowBase):
    """Workflow create request model."""

    id: str | None = Field(default=None, pattern=_KEY_PATTERN)


class WorkflowUpdate(BaseModel):
    """Workflow update request model."""

    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    scenario: Literal["general", "editor_rewrite", "project_pipeline"] | None = None
    input_schema: list[WorkflowInputDef] | None = None
    entry_node_id: str | None = Field(default=None, pattern=_KEY_PATTERN)
    nodes: list[WorkflowNode] | None = None

    @model_validator(mode="after")
    def validate_non_empty(self) -> WorkflowUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")
        return self


class WorkflowRunRecord(BaseModel):
    """One workflow run history record."""

    run_id: str
    workflow_id: str
    status: Literal["success", "error"]
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0)
    inputs: dict[str, Any] = Field(default_factory=dict)
    output: str | None = None
    node_outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class WorkflowRunHistory(BaseModel):
    """Workflow run history file schema."""

    runs: list[WorkflowRunRecord] = Field(default_factory=list)
