"""
Assistant configuration data models

Defines Pydantic models for AI assistants with system prompts and sampling parameters.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class Assistant(BaseModel):
    """AI Assistant configuration"""
    id: str = Field(..., description="Assistant unique identifier")
    name: str = Field(..., description="Assistant display name")
    description: Optional[str] = Field(None, description="Assistant description")
    model_id: str = Field(..., description="Model composite ID (provider_id:model_id)")
    system_prompt: Optional[str] = Field(None, description="System prompt for the assistant")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature for this assistant")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Max output tokens (None = provider default)")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Top-p nucleus sampling")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-k sampling")
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Presence penalty")
    max_rounds: Optional[int] = Field(None, description="Maximum conversation rounds to keep (-1 = unlimited, None = unlimited)")
    enabled: bool = Field(default=True, description="Whether assistant is enabled")


class AssistantsConfig(BaseModel):
    """Complete assistants configuration"""
    default: str = Field(..., description="Default assistant ID")
    assistants: List[Assistant]


class AssistantCreate(BaseModel):
    """Create assistant request"""
    id: str = Field(..., description="Assistant unique identifier")
    name: str = Field(..., description="Assistant display name")
    description: Optional[str] = Field(None, description="Assistant description")
    model_id: str = Field(..., description="Model composite ID (provider_id:model_id)")
    system_prompt: Optional[str] = Field(None, description="System prompt for the assistant")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Max output tokens (None = provider default)")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Top-p nucleus sampling")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-k sampling")
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Presence penalty")
    max_rounds: Optional[int] = Field(None, description="Maximum conversation rounds (-1 = unlimited)")
    enabled: bool = Field(default=True, description="Whether assistant is enabled")


class AssistantUpdate(BaseModel):
    """Update assistant request"""
    name: Optional[str] = Field(None, description="Assistant display name")
    description: Optional[str] = Field(None, description="Assistant description")
    model_id: Optional[str] = Field(None, description="Model composite ID (provider_id:model_id)")
    system_prompt: Optional[str] = Field(None, description="System prompt for the assistant")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Max output tokens (None = provider default)")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Top-p nucleus sampling")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-k sampling")
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Presence penalty")
    max_rounds: Optional[int] = Field(None, description="Maximum conversation rounds (-1 = unlimited)")
    enabled: Optional[bool] = Field(None, description="Whether assistant is enabled")
