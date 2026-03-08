"""Shared definitions for request-scoped tools."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .definitions import ToolDefinition


class WebSearchArgs(BaseModel):
    """Arguments for web_search tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query for public web search.",
    )


class ReadWebpageArgs(BaseModel):
    """Arguments for read_webpage tool."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Absolute webpage URL to fetch and summarize for research use.",
    )


WEB_SEARCH_TOOL = ToolDefinition(
    name="web_search",
    description=(
        "Search the public web and return structured results with title, URL, and snippet. "
        "Use this when you need up-to-date external information."
    ),
    args_schema=WebSearchArgs,
    group="web",
    source="web",
    enabled_by_default=False,
)


READ_WEBPAGE_TOOL = ToolDefinition(
    name="read_webpage",
    description=(
        "Fetch and read a webpage URL, returning the title, final URL, and extracted main content."
    ),
    args_schema=ReadWebpageArgs,
    group="web",
    source="web",
    enabled_by_default=False,
)


class SearchKnowledgeArgs(BaseModel):
    """Arguments for search_knowledge tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query for assistant-bound knowledge bases.",
    )
    top_k: int = Field(5, ge=1, le=8, description="Maximum number of hits to return (1-8).")
    include_diagnostics: bool = Field(
        False,
        description="Include compact retrieval diagnostics in the response.",
    )


class ReadKnowledgeArgs(BaseModel):
    """Arguments for read_knowledge tool."""

    refs: List[str] = Field(
        ...,
        min_length=1,
        max_length=8,
        description="ref_id values from search_knowledge, e.g. kb:foo|doc:bar|chunk:3.",
    )
    max_chars: int = Field(
        6000,
        ge=1000,
        le=12000,
        description="Total character cap for all returned content; output is truncated when reached.",
    )
    neighbor_window: int = Field(
        0,
        ge=0,
        le=2,
        description="Include plus or minus N adjacent chunks around each requested chunk.",
    )


SEARCH_KNOWLEDGE_TOOL = ToolDefinition(
    name="search_knowledge",
    description=(
        "Search assistant-bound knowledge bases and return ranked hits with ref_id. "
        "Call this before read_knowledge."
    ),
    args_schema=SearchKnowledgeArgs,
    group="knowledge",
    source="rag",
    enabled_by_default=True,
    requires_project_knowledge=True,
)


READ_KNOWLEDGE_TOOL = ToolDefinition(
    name="read_knowledge",
    description=(
        "Read chunk content for ref_id values from search_knowledge. "
        "Returns at most max_chars characters across all requested refs."
    ),
    args_schema=ReadKnowledgeArgs,
    group="knowledge",
    source="rag",
    enabled_by_default=True,
    requires_project_knowledge=True,
)


class ReadCurrentDocumentArgs(BaseModel):
    """Arguments for read_current_document."""

    start_line: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-based start line (inclusive). Omit to read from the first line.",
    )
    end_line: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-based end line (inclusive). Omit to read through the last line.",
    )
    max_chars: int = Field(
        default=12000,
        ge=500,
        le=120000,
        description="Maximum characters to return; content is truncated when this limit is reached.",
    )


class ApplyDiffCurrentDocumentArgs(BaseModel):
    """Arguments for apply_diff_current_document."""

    unified_diff: str = Field(
        ...,
        min_length=1,
        max_length=300000,
        description="Single-file unified diff targeting the active document.",
    )
    base_hash: str = Field(
        ...,
        min_length=16,
        max_length=128,
        description="content_hash returned by read_current_document; must match latest file content.",
    )
    dry_run: bool = Field(
        default=True,
        description="Preview only. Must stay true; final apply requires explicit confirmation.",
    )


class SearchProjectTextArgs(BaseModel):
    """Arguments for search_project_text."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Text or regex pattern to match.",
    )
    case_sensitive: bool = Field(default=False, description="Enable case-sensitive matching.")
    use_regex: bool = Field(default=False, description="Treat query as a regular expression.")
    include_glob: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional include glob, for example **/*.py.",
    )
    exclude_glob: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional exclude glob, for example **/node_modules/**.",
    )
    max_results: int = Field(
        default=30,
        ge=1,
        le=200,
        description="Maximum number of matches to return.",
    )
    context_lines: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Number of context lines before and after each match.",
    )
    max_chars_per_line: int = Field(
        default=300,
        ge=80,
        le=1200,
        description="Maximum characters per returned line; longer lines are clipped.",
    )


class ReadProjectDocumentArgs(BaseModel):
    """Arguments for read_project_document."""

    file_path: str = Field(
        ...,
        min_length=1,
        max_length=800,
        description="Project-relative file path to read.",
    )
    start_line: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-based start line (inclusive). Omit to read from the first line.",
    )
    end_line: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-based end line (inclusive). Omit to read through the last line.",
    )
    max_chars: int = Field(
        default=12000,
        ge=500,
        le=120000,
        description="Maximum characters to return; content is truncated when this limit is reached.",
    )


class ApplyDiffProjectDocumentArgs(BaseModel):
    """Arguments for apply_diff_project_document."""

    file_path: str = Field(
        ...,
        min_length=1,
        max_length=800,
        description="Project-relative file path to patch.",
    )
    unified_diff: str = Field(
        ...,
        min_length=1,
        max_length=300000,
        description="Single-file unified diff targeting file_path.",
    )
    base_hash: str = Field(
        ...,
        min_length=16,
        max_length=128,
        description="content_hash returned by read_project_document or read_current_document.",
    )
    dry_run: bool = Field(
        default=True,
        description="Preview only. Must stay true; final apply requires explicit confirmation.",
    )


READ_PROJECT_DOCUMENT_TOOL = ToolDefinition(
    name="read_project_document",
    description=(
        "Read any project file by path and return content with content_hash. "
        "Output may be truncated by max_chars. "
        "Call this before apply_diff_project_document."
    ),
    args_schema=ReadProjectDocumentArgs,
    group="projectDocuments",
    source="project_document",
    enabled_by_default=True,
)


APPLY_DIFF_PROJECT_DOCUMENT_TOOL = ToolDefinition(
    name="apply_diff_project_document",
    description=(
        "Preview a unified diff patch for a project file. "
        "base_hash must match read_project_document.content_hash for the same file_path. "
        "This tool only supports dry_run=true and returns pending_patch_id for confirmation."
    ),
    args_schema=ApplyDiffProjectDocumentArgs,
    group="projectDocuments",
    source="project_document",
    enabled_by_default=False,
)


READ_CURRENT_DOCUMENT_TOOL = ToolDefinition(
    name="read_current_document",
    description=(
        "Read the active project file and return content with content_hash. "
        "Output may be truncated by max_chars. "
        "Call this before apply_diff_current_document."
    ),
    args_schema=ReadCurrentDocumentArgs,
    group="projectDocuments",
    source="project_document",
    enabled_by_default=True,
)


APPLY_DIFF_CURRENT_DOCUMENT_TOOL = ToolDefinition(
    name="apply_diff_current_document",
    description=(
        "Preview a unified diff patch for the active file. "
        "base_hash must match read_current_document.content_hash. "
        "This tool only supports dry_run=true and returns pending_patch_id for confirmation."
    ),
    args_schema=ApplyDiffCurrentDocumentArgs,
    group="projectDocuments",
    source="project_document",
    enabled_by_default=False,
)


SEARCH_PROJECT_TEXT_TOOL = ToolDefinition(
    name="search_project_text",
    description=(
        "Search text across project files and return matching snippets. "
        "Supports regex, glob filters, and capped results for cross-file discovery."
    ),
    args_schema=SearchProjectTextArgs,
    group="projectDocuments",
    source="project_document",
    enabled_by_default=True,
)


REQUEST_SCOPED_TOOL_DEFINITIONS = [
    WEB_SEARCH_TOOL,
    READ_WEBPAGE_TOOL,
    READ_PROJECT_DOCUMENT_TOOL,
    READ_CURRENT_DOCUMENT_TOOL,
    SEARCH_PROJECT_TEXT_TOOL,
    APPLY_DIFF_PROJECT_DOCUMENT_TOOL,
    APPLY_DIFF_CURRENT_DOCUMENT_TOOL,
    SEARCH_KNOWLEDGE_TOOL,
    READ_KNOWLEDGE_TOOL,
]


def get_request_scoped_tool_default_enabled_map() -> Dict[str, bool]:
    """Project-level default enabled state for non-builtin tools."""
    return {
        definition.name: definition.enabled_by_default
        for definition in REQUEST_SCOPED_TOOL_DEFINITIONS
    }
