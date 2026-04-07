"""Builtin tool: execute_javascript."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..definitions import ToolDefinition


class ExecuteJavaScriptArgs(BaseModel):
    """Arguments for execute_javascript."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="JavaScript code to execute in the browser runtime.",
    )
    timeout_ms: int = Field(
        30000,
        ge=1000,
        le=120000,
        description="Execution timeout in milliseconds.",
    )


TOOL = ToolDefinition(
    name="execute_javascript",
    description=(
        "Execute JavaScript code in a browser-side sandbox and return stdout/stderr/result as JSON text."
    ),
    args_schema=ExecuteJavaScriptArgs,
    group="builtin",
    source="builtin",
    enabled_by_default=True,
)


def execute(*, code: str, timeout_ms: int = 30000) -> str:
    """Request-level execution is handled by chat runtime; registry fallback is explicit."""
    _ = code
    _ = timeout_ms
    return (
        "Error: execute_javascript requires a live chat client runtime and cannot run server-side"
    )


def build_tool():
    """Build the LangChain tool instance."""
    return TOOL.build_tool(func=execute)
