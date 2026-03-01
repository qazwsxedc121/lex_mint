"""Workflow configuration and run history models."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


_KEY_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"


class WorkflowInputDef(BaseModel):
    """Input schema entry for one workflow parameter."""

    key: str = Field(..., pattern=_KEY_PATTERN)
    type: Literal["string", "number", "boolean"] = "string"
    required: bool = False
    default: Optional[Union[str, int, float, bool]] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_default_type(self) -> "WorkflowInputDef":
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
    model_id: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    output_key: Optional[str] = Field(default=None, pattern=_KEY_PATTERN)
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
    result_template: Optional[str] = None


WorkflowNode = Annotated[
    Union[StartNode, LlmNode, ConditionNode, EndNode],
    Field(discriminator="type"),
]


class WorkflowBase(BaseModel):
    """Shared workflow fields."""

    name: str
    description: Optional[str] = None
    enabled: bool = True
    scenario: Literal["general", "editor_rewrite"] = "general"
    is_system: bool = False
    template_version: Optional[int] = Field(default=None, ge=1)
    input_schema: List[WorkflowInputDef] = Field(default_factory=list)
    entry_node_id: str = Field(..., pattern=_KEY_PATTERN)
    nodes: List[WorkflowNode] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Workflow name cannot be empty")
        return stripped

    @field_validator("input_schema")
    @classmethod
    def validate_unique_input_keys(cls, value: List[WorkflowInputDef]) -> List[WorkflowInputDef]:
        seen = set()
        for item in value:
            key_lower = item.key.lower()
            if key_lower in seen:
                raise ValueError(f"Duplicate input key '{item.key}'")
            seen.add(key_lower)
        return value

    @model_validator(mode="after")
    def validate_graph(self) -> "WorkflowBase":
        if not self.nodes:
            raise ValueError("Workflow must include at least one node")

        node_ids: set[str] = set()
        has_start = False
        has_end = False

        for node in self.nodes:
            if node.id in node_ids:
                raise ValueError(f"Duplicate node id '{node.id}'")
            node_ids.add(node.id)
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

        for node in self.nodes:
            targets: List[str] = []
            if isinstance(node, StartNode):
                targets = [node.next_id]
            elif isinstance(node, LlmNode):
                targets = [node.next_id]
            elif isinstance(node, ConditionNode):
                targets = [node.true_next_id, node.false_next_id]

            for target in targets:
                if target not in node_ids:
                    raise ValueError(
                        f"Node '{node.id}' references missing next node '{target}'"
                    )

        return self


class Workflow(WorkflowBase):
    """Persisted workflow."""

    id: str = Field(..., pattern=_KEY_PATTERN)
    created_at: datetime
    updated_at: datetime


class WorkflowsConfig(BaseModel):
    """Workflow config file schema."""

    workflows: List[Workflow] = Field(default_factory=list)


class WorkflowCreate(WorkflowBase):
    """Workflow create request model."""

    id: Optional[str] = Field(default=None, pattern=_KEY_PATTERN)


class WorkflowUpdate(BaseModel):
    """Workflow update request model."""

    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    scenario: Optional[Literal["general", "editor_rewrite"]] = None
    input_schema: Optional[List[WorkflowInputDef]] = None
    entry_node_id: Optional[str] = Field(default=None, pattern=_KEY_PATTERN)
    nodes: Optional[List[WorkflowNode]] = None

    @model_validator(mode="after")
    def validate_non_empty(self) -> "WorkflowUpdate":
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
    inputs: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[str] = None
    node_outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class WorkflowRunHistory(BaseModel):
    """Workflow run history file schema."""

    runs: List[WorkflowRunRecord] = Field(default_factory=list)
