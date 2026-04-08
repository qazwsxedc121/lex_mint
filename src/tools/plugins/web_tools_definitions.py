"""Tool definitions for web plugin tools."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.tools.definitions import ToolDefinition


class WebSearchArgs(BaseModel):
    """Arguments for web_search tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query for public web search.",
    )
    page: int = Field(
        1,
        ge=1,
        le=5,
        description="1-based result page. Use page>1 to explore beyond the first result batch.",
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
        "Use this when you need up-to-date external information or need to find the next page to read. "
        "Prefer specific queries with entities, dates, site names, and page types such as roster, discography, "
        "results, paper, or table. Avoid repeating broad searches that already failed. "
        "If the first page is noisy, request a later page instead of repeating the exact same search."
    ),
    args_schema=WebSearchArgs,
    group="web",
    source="web",
    enabled_by_default=False,
)


READ_WEBPAGE_TOOL = ToolDefinition(
    name="read_webpage",
    description=(
        "Fetch and read a webpage URL, returning the title, final URL, and extracted main content. "
        "Use this on promising URLs from web_search to verify the exact answer. If one page is insufficient, "
        "do another targeted web_search for a more specific page instead of guessing."
    ),
    args_schema=ReadWebpageArgs,
    group="web",
    source="web",
    enabled_by_default=False,
)
