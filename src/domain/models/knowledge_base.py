"""
Knowledge Base data models

Defines Pydantic models for knowledge bases and their documents.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeBase(BaseModel):
    """Knowledge base configuration"""

    id: str = Field(..., description="Knowledge base unique identifier")
    name: str = Field(..., description="Knowledge base display name")
    description: str | None = Field(default=None, description="Knowledge base description")
    embedding_model: str | None = Field(
        default=None, description="Override embedding model (provider:model format)"
    )
    chunk_size: int | None = Field(
        default=None, ge=100, le=10000, description="Override chunk size"
    )
    chunk_overlap: int | None = Field(
        default=None, ge=0, le=5000, description="Override chunk overlap"
    )
    document_count: int = Field(default=0, description="Number of documents")
    enabled: bool = Field(default=True, description="Whether knowledge base is enabled")
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="Creation timestamp"
    )


class KnowledgeBaseDocument(BaseModel):
    """Document within a knowledge base"""

    id: str = Field(..., description="Document unique identifier")
    kb_id: str = Field(..., description="Parent knowledge base ID")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File extension (e.g., .pdf, .md)")
    file_size: int = Field(default=0, description="File size in bytes")
    status: str = Field(
        default="pending", description="Processing status: pending, processing, ready, error"
    )
    chunk_count: int = Field(default=0, description="Number of chunks created")
    error_message: str | None = Field(
        default=None, description="Error message if processing failed"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="Creation timestamp"
    )


class KnowledgeBasesConfig(BaseModel):
    """Complete knowledge bases configuration"""

    knowledge_bases: list[KnowledgeBase] = Field(default_factory=list)
    documents: list[KnowledgeBaseDocument] = Field(default_factory=list)


class KnowledgeBaseCreate(BaseModel):
    """Create knowledge base request"""

    id: str = Field(..., description="Knowledge base unique identifier")
    name: str = Field(..., description="Knowledge base display name")
    description: str | None = Field(default=None, description="Knowledge base description")
    embedding_model: str | None = Field(default=None, description="Override embedding model")
    chunk_size: int | None = Field(
        default=None, ge=100, le=10000, description="Override chunk size"
    )
    chunk_overlap: int | None = Field(
        default=None, ge=0, le=5000, description="Override chunk overlap"
    )
    enabled: bool = Field(default=True, description="Whether knowledge base is enabled")


class KnowledgeBaseUpdate(BaseModel):
    """Update knowledge base request"""

    name: str | None = Field(default=None, description="Knowledge base display name")
    description: str | None = Field(default=None, description="Knowledge base description")
    embedding_model: str | None = Field(default=None, description="Override embedding model")
    chunk_size: int | None = Field(
        default=None, ge=100, le=10000, description="Override chunk size"
    )
    chunk_overlap: int | None = Field(
        default=None, ge=0, le=5000, description="Override chunk overlap"
    )
    enabled: bool | None = Field(default=None, description="Whether knowledge base is enabled")


class KnowledgeBaseChunk(BaseModel):
    """Chunk entry from a knowledge base collection (developer inspection)"""

    id: str = Field(..., description="Chunk unique identifier")
    kb_id: str = Field(..., description="Knowledge base ID")
    doc_id: str | None = Field(default=None, description="Document ID")
    filename: str | None = Field(default=None, description="Source filename")
    chunk_index: int = Field(default=0, description="Chunk index within the document")
    content: str = Field(..., description="Chunk text content")
