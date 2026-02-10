"""
Prompt template configuration data models
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class PromptTemplate(BaseModel):
    """Reusable prompt template definition."""
    id: str = Field(..., description="Template unique identifier")
    name: str = Field(..., description="Template display name")
    description: Optional[str] = Field(None, description="Template description")
    content: str = Field(..., description="Prompt template content")
    enabled: bool = Field(default=True, description="Whether template is enabled")


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


class PromptTemplateUpdate(BaseModel):
    """Update prompt template request."""
    name: Optional[str] = Field(None, description="Template display name")
    description: Optional[str] = Field(None, description="Template description")
    content: Optional[str] = Field(None, description="Prompt template content")
    enabled: Optional[bool] = Field(None, description="Whether template is enabled")
