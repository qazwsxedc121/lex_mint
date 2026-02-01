"""Project configuration data models."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from pathlib import Path
from datetime import datetime


class Project(BaseModel):
    """Project configuration."""

    id: str = Field(..., description="Unique project ID")
    name: str = Field(..., description="Project display name")
    root_path: str = Field(..., description="Absolute path to project root directory")
    description: Optional[str] = Field(None, description="Project description")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator('root_path')
    @classmethod
    def validate_root_path(cls, v: str) -> str:
        """Validate that root_path is an absolute path to an existing directory."""
        path = Path(v)
        if not path.is_absolute():
            raise ValueError("root_path must be absolute path")
        if not path.exists():
            raise ValueError(f"Path does not exist: {v}")
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {v}")
        return str(path)


class ProjectsConfig(BaseModel):
    """Container for all projects."""

    projects: List[Project] = Field(default_factory=list)


class ProjectCreate(BaseModel):
    """Request model for creating project."""

    name: str = Field(..., min_length=1, max_length=100)
    root_path: str
    description: Optional[str] = Field(None, max_length=500)


class ProjectUpdate(BaseModel):
    """Request model for updating project."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    root_path: Optional[str] = None
    description: Optional[str] = None


class FileNode(BaseModel):
    """File tree node."""

    name: str = Field(..., description="File/directory name")
    path: str = Field(..., description="Relative path from project root")
    type: str = Field(..., description="'file' or 'directory'")
    size: Optional[int] = Field(None, description="File size in bytes (files only)")
    modified_at: Optional[str] = Field(None, description="Last modified timestamp")
    children: Optional[List['FileNode']] = Field(None, description="Child nodes (directories only)")


class FileContent(BaseModel):
    """File content response."""

    path: str = Field(..., description="Relative path from project root")
    content: str = Field(..., description="File content")
    encoding: str = Field(default="utf-8", description="File encoding")
    size: int = Field(..., description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type")


class FileWrite(BaseModel):
    """File write request."""

    path: str = Field(..., description="Relative path from project root")
    content: str = Field(..., description="File content to write")
    encoding: str = Field(default="utf-8", description="File encoding")
