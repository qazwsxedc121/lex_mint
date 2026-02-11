"""Search-related data models."""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class SearchSource(BaseModel):
    """Single web search source item."""

    type: Optional[Literal["search", "webpage", "rag", "memory"]] = Field(
        None,
        description="Source type: search, webpage, rag, or memory"
    )
    title: Optional[str] = Field(None, description="Result title")
    url: Optional[str] = Field(None, description="Result URL")
    snippet: Optional[str] = Field(None, description="Short snippet or summary")
    score: Optional[float] = Field(None, description="Relevance score if provided")

    # Memory-specific fields (optional)
    id: Optional[str] = Field(None, description="Memory item ID")
    scope: Optional[Literal["global", "assistant"]] = Field(None, description="Memory scope")
    layer: Optional[Literal["identity", "preference", "context", "experience", "activity"]] = Field(None, description="Memory layer")

    # RAG-specific fields (optional)
    content: Optional[str] = Field(None, description="RAG chunk content")
    kb_id: Optional[str] = Field(None, description="Knowledge base ID")
    doc_id: Optional[str] = Field(None, description="Knowledge base document ID")
    filename: Optional[str] = Field(None, description="Document filename")
    chunk_index: Optional[int] = Field(None, description="Chunk index in document")
