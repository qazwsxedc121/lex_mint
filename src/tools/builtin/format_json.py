"""Builtin tool: format_json."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from ..definitions import ToolDefinition


class FormatJsonArgs(BaseModel):
    """Arguments for format_json."""

    value: str = Field(
        ...,
        min_length=1,
        description="JSON string to validate and format.",
    )
    indent: int = Field(
        default=2,
        ge=0,
        le=8,
        description="Indent width used when pretty-printing the JSON payload.",
    )
    sort_keys: bool = Field(
        default=False,
        description="Whether to sort object keys alphabetically in the formatted result.",
    )


TOOL = ToolDefinition(
    name="format_json",
    description="Validate and format a JSON string for inspection or reuse.",
    args_schema=FormatJsonArgs,
    group="builtin",
    source="builtin",
    enabled_by_default=False,
)


def execute(*, value: str, indent: int = 2, sort_keys: bool = False) -> str:
    """Validate and pretty-print JSON content."""
    try:
        parsed = json.loads(value)
        separators = (",", ":") if indent == 0 else None
        return json.dumps(
            parsed,
            ensure_ascii=False,
            indent=indent or None,
            sort_keys=sort_keys,
            separators=separators,
        )
    except Exception as exc:
        return f"Error: Invalid JSON - {exc}"


def build_tool():
    """Build the LangChain tool instance."""
    return TOOL.build_tool(func=execute)
