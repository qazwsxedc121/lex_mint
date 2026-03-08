"""Builtin tool: text_statistics."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from ..definitions import ToolDefinition


class TextStatisticsArgs(BaseModel):
    """Arguments for text_statistics."""

    text: str = Field(
        ...,
        description="Text to analyze for length and token-like counts.",
    )


TOOL = ToolDefinition(
    name="text_statistics",
    description="Count characters, words, lines, and UTF-8 bytes for a text payload.",
    args_schema=TextStatisticsArgs,
    group="builtin",
    source="builtin",
    enabled_by_default=False,
)


def execute(*, text: str) -> str:
    """Return basic statistics about a piece of text."""
    lines = text.splitlines()
    words = [part for part in text.split() if part]
    payload = {
        "chars": len(text),
        "chars_no_whitespace": sum(1 for char in text if not char.isspace()),
        "words": len(words),
        "lines": len(lines) if lines else (1 if text else 0),
        "utf8_bytes": len(text.encode("utf-8")),
    }
    return json.dumps(payload, ensure_ascii=False)


def build_tool():
    """Build the LangChain tool instance."""
    return TOOL.build_tool(func=execute)
