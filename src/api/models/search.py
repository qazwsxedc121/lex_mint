"""Search-related data models."""

from pydantic import BaseModel, Field
from typing import Optional


class SearchSource(BaseModel):
    """Single web search source item."""

    title: str = Field(..., description="Result title")
    url: str = Field(..., description="Result URL")
    snippet: Optional[str] = Field(None, description="Short snippet or summary")
    score: Optional[float] = Field(None, description="Relevance score if provided")
