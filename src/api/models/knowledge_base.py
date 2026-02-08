"""
Knowledge Base data models

Defines Pydantic models for knowledge bases and their documents.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class KnowledgeBase(BaseModel):
    """Knowledge base configuration"""
    id: str = Field(..., description="Knowledge base unique identifier")
    name: str = Field(..., description="Knowledge base display name")
    description: Optional[str] = Field(None, description="Knowledge base description")
    embedding_model: Optional[str] = Field(None, description="Override embedding model (provider:model format)")
    chunk_size: Optional[int] = Field(None, ge=100, le=10000, description="Override chunk size")
    chunk_overlap: Optional[int] = Field(None, ge=0, le=5000, description="Override chunk overlap")
    document_count: int = Field(default=0, description="Number of documents")
    enabled: bool = Field(default=True, description="Whether knowledge base is enabled")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Creation timestamp")


class KnowledgeBaseDocument(BaseModel):
    """Document within a knowledge base"""
    id: str = Field(..., description="Document unique identifier")
    kb_id: str = Field(..., description="Parent knowledge base ID")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File extension (e.g., .pdf, .md)")
    file_size: int = Field(default=0, description="File size in bytes")
    status: str = Field(default="pending", description="Processing status: pending, processing, ready, error")
    chunk_count: int = Field(default=0, description="Number of chunks created")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Creation timestamp")


class KnowledgeBasesConfig(BaseModel):
    """Complete knowledge bases configuration"""
    knowledge_bases: List[KnowledgeBase] = Field(default_factory=list)
    documents: List[KnowledgeBaseDocument] = Field(default_factory=list)


class KnowledgeBaseCreate(BaseModel):
    """Create knowledge base request"""
    id: str = Field(..., description="Knowledge base unique identifier")
    name: str = Field(..., description="Knowledge base display name")
    description: Optional[str] = Field(None, description="Knowledge base description")
    embedding_model: Optional[str] = Field(None, description="Override embedding model")
    chunk_size: Optional[int] = Field(None, ge=100, le=10000, description="Override chunk size")
    chunk_overlap: Optional[int] = Field(None, ge=0, le=5000, description="Override chunk overlap")
    enabled: bool = Field(default=True, description="Whether knowledge base is enabled")


class KnowledgeBaseUpdate(BaseModel):
    """Update knowledge base request"""
    name: Optional[str] = Field(None, description="Knowledge base display name")
    description: Optional[str] = Field(None, description="Knowledge base description")
    embedding_model: Optional[str] = Field(None, description="Override embedding model")
    chunk_size: Optional[int] = Field(None, ge=100, le=10000, description="Override chunk size")
    chunk_overlap: Optional[int] = Field(None, ge=0, le=5000, description="Override chunk overlap")
    enabled: Optional[bool] = Field(None, description="Whether knowledge base is enabled")
