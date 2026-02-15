"""
Prompt template configuration data models
"""
import re
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


_VARIABLE_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RESERVED_VARIABLE_KEYS = {"cursor"}


class PromptTemplateVariable(BaseModel):
    """Schema for one template variable."""
    key: str = Field(..., description="Variable key used in template placeholders")
    label: Optional[str] = Field(None, description="Display label in fill form")
    description: Optional[str] = Field(None, description="Variable help text")
    type: Literal["text", "number", "boolean", "select"] = Field(
        default="text",
        description="Input type used for this variable"
    )
    required: bool = Field(default=False, description="Whether variable value is required")
    default: Optional[Any] = Field(None, description="Default value for this variable")
    options: List[str] = Field(default_factory=list, description="Allowed values when type=select")

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        stripped = value.strip()
        if not _VARIABLE_KEY_PATTERN.match(stripped):
            raise ValueError("Variable key must match ^[A-Za-z_][A-Za-z0-9_]*$")
        if stripped.lower() in _RESERVED_VARIABLE_KEYS:
            raise ValueError("Variable key 'cursor' is reserved")
        return stripped

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: List[str]) -> List[str]:
        normalized = [item.strip() for item in value if item and item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Variable options must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_type_specific_rules(self) -> "PromptTemplateVariable":
        if self.type == "select":
            if not self.options:
                raise ValueError("Select variable must provide non-empty options")
            if self.default is not None:
                if not isinstance(self.default, str):
                    raise ValueError("Select variable default must be a string")
                if self.default not in self.options:
                    raise ValueError("Select variable default must be one of the options")
            return self

        if self.options:
            raise ValueError("Only select variables may define options")

        if self.default is None:
            return self

        if self.type == "text" and not isinstance(self.default, str):
            raise ValueError("Text variable default must be a string")
        if self.type == "number" and (
            isinstance(self.default, bool) or not isinstance(self.default, (int, float))
        ):
            raise ValueError("Number variable default must be a number")
        if self.type == "boolean" and not isinstance(self.default, bool):
            raise ValueError("Boolean variable default must be a boolean")
        return self


def _validate_unique_variable_keys(variables: List[PromptTemplateVariable]) -> List[PromptTemplateVariable]:
    seen = set()
    for variable in variables:
        if variable.key in seen:
            raise ValueError(f"Duplicate variable key '{variable.key}'")
        seen.add(variable.key)
    return variables


class PromptTemplate(BaseModel):
    """Reusable prompt template definition."""
    id: str = Field(..., description="Template unique identifier")
    name: str = Field(..., description="Template display name")
    description: Optional[str] = Field(None, description="Template description")
    content: str = Field(..., description="Prompt template content")
    enabled: bool = Field(default=True, description="Whether template is enabled")
    variables: List[PromptTemplateVariable] = Field(
        default_factory=list,
        description="Optional variable schema for template parameters"
    )

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, value: List[PromptTemplateVariable]) -> List[PromptTemplateVariable]:
        return _validate_unique_variable_keys(value)


class PromptTemplatesConfig(BaseModel):
    """Complete prompt templates configuration."""
    templates: List[PromptTemplate] = Field(default_factory=list)


class PromptTemplateCreate(BaseModel):
    """Create prompt template request."""
    id: Optional[str] = Field(None, description="Template unique identifier (optional, auto-generated)")
    name: str = Field(..., description="Template display name")
    description: Optional[str] = Field(None, description="Template description")
    content: str = Field(..., description="Prompt template content")
    enabled: bool = Field(default=True, description="Whether template is enabled")
    variables: List[PromptTemplateVariable] = Field(
        default_factory=list,
        description="Optional variable schema for template parameters"
    )

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, value: List[PromptTemplateVariable]) -> List[PromptTemplateVariable]:
        return _validate_unique_variable_keys(value)


class PromptTemplateUpdate(BaseModel):
    """Update prompt template request."""
    name: Optional[str] = Field(None, description="Template display name")
    description: Optional[str] = Field(None, description="Template description")
    content: Optional[str] = Field(None, description="Prompt template content")
    enabled: Optional[bool] = Field(None, description="Whether template is enabled")
    variables: Optional[List[PromptTemplateVariable]] = Field(
        None,
        description="Optional variable schema for template parameters"
    )

    @field_validator("variables")
    @classmethod
    def validate_variables(
        cls, value: Optional[List[PromptTemplateVariable]]
    ) -> Optional[List[PromptTemplateVariable]]:
        if value is None:
            return value
        return _validate_unique_variable_keys(value)
