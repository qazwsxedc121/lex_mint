"""Project configuration data models."""

from datetime import datetime
import os
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from src.tools.builtin import get_builtin_tool_default_enabled_map
from src.tools.request_scoped import get_request_scoped_tool_default_enabled_map


DEFAULT_PROJECT_TOOL_ENABLED_MAP: Dict[str, bool] = {
    **get_builtin_tool_default_enabled_map(),
    **get_request_scoped_tool_default_enabled_map(),
}


def get_default_project_tool_enabled_map() -> Dict[str, bool]:
    return dict(DEFAULT_PROJECT_TOOL_ENABLED_MAP)


class ProjectRagSettings(BaseModel):
    """Project-scoped retrieval settings."""

    knowledge_base_ids: List[str] = Field(default_factory=list, description="Knowledge base IDs available to this project")
    knowledge_base_mode: Literal["append", "override"] = Field(
        default="append",
        description="How project knowledge bases interact with assistant-bound knowledge bases",
    )

    @field_validator('knowledge_base_ids', mode='before')
    @classmethod
    def normalize_knowledge_base_ids(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("knowledge_base_ids must be a list")

        normalized: List[str] = []
        seen = set()
        for item in value:
            kb_id = str(item or '').strip()
            if not kb_id or kb_id in seen:
                continue
            normalized.append(kb_id)
            seen.add(kb_id)
        return normalized


class ProjectSettings(BaseModel):
    """Project-scoped settings persisted with the project config."""

    rag: ProjectRagSettings = Field(default_factory=ProjectRagSettings)
    tools: 'ProjectToolSettings' = Field(default_factory=lambda: ProjectToolSettings())


class ProjectToolSettings(BaseModel):
    """Project-scoped tool availability settings."""

    tool_enabled_map: Dict[str, bool] = Field(
        default_factory=get_default_project_tool_enabled_map,
        description="Per-tool enablement for project-scoped chat and agent flows",
    )

    @field_validator('tool_enabled_map', mode='before')
    @classmethod
    def normalize_tool_enabled_map(cls, value: Any) -> Dict[str, bool]:
        merged = get_default_project_tool_enabled_map()
        if value is None:
            return merged
        if not isinstance(value, dict):
            raise ValueError("tool_enabled_map must be an object")

        for raw_key, raw_enabled in value.items():
            key = str(raw_key or '').strip()
            if not key:
                continue
            merged[key] = bool(raw_enabled)
        return merged


class Project(BaseModel):
    """Project configuration."""

    id: str = Field(..., description="Unique project ID")
    name: str = Field(..., description="Project display name")
    root_path: str = Field(..., description="Absolute path to project root directory")
    description: Optional[str] = Field(default=None, description="Project description")
    settings: ProjectSettings = Field(default_factory=ProjectSettings, description="Project-specific settings")
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
    settings: Optional[ProjectSettings] = None


class ProjectUpdate(BaseModel):
    """Request model for updating project."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    root_path: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[ProjectSettings] = None


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
    content_hash: Optional[str] = Field(default=None, description="SHA-256 hash of content")
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
    expected_hash: Optional[str] = Field(
        default=None,
        min_length=16,
        max_length=128,
        description="Optional optimistic-lock hash from last read",
    )


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


ProjectWorkspaceItemType = Literal["file", "session", "run"]


def _normalize_project_relative_path(value: str) -> str:
    normalized = (value or "").replace("\\", "/").strip()
    if not normalized:
        raise ValueError("path must not be empty")
    if normalized.startswith("/"):
        raise ValueError("path must be relative")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("path must be a safe relative path")
    return str(pure)


class ProjectWorkspaceRecentItem(BaseModel):
    """One recent workspace item stored in the project-local state file."""

    type: ProjectWorkspaceItemType
    id: str = Field(..., min_length=1, max_length=800)
    title: str = Field(..., min_length=1, max_length=500)
    path: Optional[str] = Field(default=None, max_length=800)
    updated_at: str = Field(..., min_length=1, max_length=64)
    meta: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("path")
    @classmethod
    def validate_optional_path(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_project_relative_path(value)


class ProjectWorkspaceState(BaseModel):
    """Project-local workspace state stored in .lex_mint/state/."""

    version: int = Field(default=1, ge=1)
    project_id: str = Field(..., min_length=1, max_length=200)
    updated_at: Optional[str] = Field(default=None, max_length=64)
    recent_items: List[ProjectWorkspaceRecentItem] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)


class ProjectWorkspaceItemUpsert(BaseModel):
    """Request model for adding/updating a recent workspace item."""

    type: ProjectWorkspaceItemType
    id: str = Field(..., min_length=1, max_length=800)
    title: str = Field(..., min_length=1, max_length=500)
    path: Optional[str] = Field(default=None, max_length=800)
    updated_at: Optional[str] = Field(default=None, max_length=64)
    meta: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("path")
    @classmethod
    def validate_optional_item_path(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_project_relative_path(value)
