"""Project configuration data models."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from pathlib import Path
import os
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
        expanded = os.path.expandvars(v)
        path = Path(expanded).expanduser()
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


class FileCreate(BaseModel):
    """File create request."""

    path: str = Field(..., description="Relative path from project root")
    content: str = Field(default="", description="Initial file content")
    encoding: str = Field(default="utf-8", description="File encoding")


class FileWrite(BaseModel):
    """File write request."""

    path: str = Field(..., description="Relative path from project root")
    content: str = Field(..., description="File content to write")
    encoding: str = Field(default="utf-8", description="File encoding")


class FileRename(BaseModel):
    """Rename request for file or directory."""

    source_path: str = Field(..., description="Relative path from project root")
    target_path: str = Field(..., description="New relative path from project root")


class FileRenameResult(BaseModel):
    """Rename result metadata."""

    old_path: str = Field(..., description="Original relative path")
    new_path: str = Field(..., description="New relative path")
    type: str = Field(..., description="'file' or 'directory'")
    size: Optional[int] = Field(None, description="File size in bytes (files only)")
    modified_at: Optional[str] = Field(None, description="Last modified timestamp")


class DirectoryCreate(BaseModel):
    """Directory create request."""

    path: str = Field(..., description="Relative path from project root")


class DirectoryEntry(BaseModel):
    """Directory entry for server-side browsing."""

    name: str = Field(..., description="Directory name")
    path: str = Field(..., description="Absolute directory path on server")
    is_dir: bool = Field(default=True, description="Whether entry is a directory")


class BrowseDirectoryCreate(BaseModel):
    """Request model for creating a directory while browsing server paths."""

    parent_path: str = Field(..., description="Absolute parent directory path on server")
    name: str = Field(..., min_length=1, max_length=255, description="New directory name")
