"""
Assistant configuration data models.

Defines Pydantic models for AI assistants with system prompts, sampling parameters,
and assistant-scoped tool policy.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.tools.builtin import get_builtin_tool_default_enabled_map
from src.tools.request_scoped import get_request_scoped_tool_default_enabled_map

DEFAULT_ASSISTANT_TOOL_ENABLED_MAP: dict[str, bool] = {
    **get_builtin_tool_default_enabled_map(),
    **get_request_scoped_tool_default_enabled_map(),
}


def get_default_assistant_tool_enabled_map() -> dict[str, bool]:
    return dict(DEFAULT_ASSISTANT_TOOL_ENABLED_MAP)


class Assistant(BaseModel):
    """AI Assistant configuration"""

    id: str = Field(..., description="Assistant unique identifier")
    name: str = Field(..., description="Assistant display name")
    description: str | None = Field(default=None, description="Assistant description")
    model_id: str = Field(..., description="Model composite ID (provider_id:model_id)")
    system_prompt: str | None = Field(default=None, description="System prompt for the assistant")
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Temperature for this assistant"
    )
    max_tokens: int | None = Field(
        default=None, ge=1, description="Max output tokens (None = provider default)"
    )
    top_p: float | None = Field(default=None, ge=0.0, le=1.0, description="Top-p nucleus sampling")
    top_k: int | None = Field(default=None, ge=1, description="Top-k sampling")
    frequency_penalty: float | None = Field(
        default=None, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    presence_penalty: float | None = Field(
        default=None, ge=-2.0, le=2.0, description="Presence penalty"
    )
    max_rounds: int | None = Field(
        default=None,
        description="Maximum conversation rounds to keep (-1 = unlimited, None = unlimited)",
    )
    icon: str | None = Field(default=None, description="Lucide icon key for the assistant avatar")
    enabled: bool = Field(default=True, description="Whether assistant is enabled")
    memory_enabled: bool = Field(
        default=False, description="Whether assistant-scoped memory is enabled"
    )
    knowledge_base_ids: list[str] | None = Field(
        default=None, description="Bound knowledge base IDs"
    )
    tool_enabled_map: dict[str, bool] = Field(
        default_factory=get_default_assistant_tool_enabled_map,
        description="Per-tool enablement for assistant-scoped tool policy",
    )

    @field_validator("tool_enabled_map", mode="before")
    @classmethod
    def normalize_tool_enabled_map(cls, value: Any) -> dict[str, bool]:
        merged = get_default_assistant_tool_enabled_map()
        if value is None:
            return merged
        if not isinstance(value, dict):
            raise ValueError("tool_enabled_map must be an object")

        for raw_key, raw_enabled in value.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            merged[key] = bool(raw_enabled)
        return merged


class AssistantsConfig(BaseModel):
    """Complete assistants configuration"""

    default: str = Field(..., description="Default assistant ID")
    assistants: list[Assistant]


class AssistantCreate(BaseModel):
    """Create assistant request"""

    id: str = Field(..., description="Assistant unique identifier")
    name: str = Field(..., description="Assistant display name")
    description: str | None = Field(default=None, description="Assistant description")
    model_id: str = Field(..., description="Model composite ID (provider_id:model_id)")
    system_prompt: str | None = Field(default=None, description="System prompt for the assistant")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int | None = Field(
        default=None, ge=1, description="Max output tokens (None = provider default)"
    )
    top_p: float | None = Field(default=None, ge=0.0, le=1.0, description="Top-p nucleus sampling")
    top_k: int | None = Field(default=None, ge=1, description="Top-k sampling")
    frequency_penalty: float | None = Field(
        default=None, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    presence_penalty: float | None = Field(
        default=None, ge=-2.0, le=2.0, description="Presence penalty"
    )
    max_rounds: int | None = Field(
        default=None, description="Maximum conversation rounds (-1 = unlimited)"
    )
    icon: str | None = Field(default=None, description="Lucide icon key for the assistant avatar")
    enabled: bool = Field(default=True, description="Whether assistant is enabled")
    memory_enabled: bool = Field(
        default=False, description="Whether assistant-scoped memory is enabled"
    )
    knowledge_base_ids: list[str] | None = Field(
        default=None, description="Bound knowledge base IDs"
    )
    tool_enabled_map: dict[str, bool] | None = Field(
        default=None,
        description="Optional per-tool enablement map override for this assistant",
    )


class AssistantUpdate(BaseModel):
    """Update assistant request"""

    name: str | None = Field(default=None, description="Assistant display name")
    description: str | None = Field(default=None, description="Assistant description")
    model_id: str | None = Field(
        default=None, description="Model composite ID (provider_id:model_id)"
    )
    system_prompt: str | None = Field(default=None, description="System prompt for the assistant")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int | None = Field(
        default=None, ge=1, description="Max output tokens (None = provider default)"
    )
    top_p: float | None = Field(default=None, ge=0.0, le=1.0, description="Top-p nucleus sampling")
    top_k: int | None = Field(default=None, ge=1, description="Top-k sampling")
    frequency_penalty: float | None = Field(
        default=None, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    presence_penalty: float | None = Field(
        default=None, ge=-2.0, le=2.0, description="Presence penalty"
    )
    max_rounds: int | None = Field(
        default=None, description="Maximum conversation rounds (-1 = unlimited)"
    )
    icon: str | None = Field(default=None, description="Lucide icon key for the assistant avatar")
    enabled: bool | None = Field(default=None, description="Whether assistant is enabled")
    memory_enabled: bool | None = Field(
        default=None, description="Whether assistant-scoped memory is enabled"
    )
    knowledge_base_ids: list[str] | None = Field(
        default=None, description="Bound knowledge base IDs"
    )
    tool_enabled_map: dict[str, bool] | None = Field(
        default=None,
        description="Optional per-tool enablement map override for this assistant",
    )
