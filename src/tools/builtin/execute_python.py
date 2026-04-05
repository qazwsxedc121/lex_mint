"""Builtin tool: execute_python."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..definitions import ToolDefinition


class ExecutePythonArgs(BaseModel):
    """Arguments for execute_python."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="Python code to execute in the client-side Pyodide runtime.",
    )
    timeout_ms: int = Field(
        30000,
        ge=1000,
        le=120000,
        description="Execution timeout in milliseconds.",
    )


TOOL = ToolDefinition(
    name="execute_python",
    description=(
        "Execute Python code in a client-side sandbox and return stdout/stderr/result as JSON text."
    ),
    args_schema=ExecutePythonArgs,
    group="builtin",
    source="builtin",
    enabled_by_default=True,
)


def execute(*, code: str, timeout_ms: int = 30000) -> str:
    """Request-level execution is handled by chat runtime; registry fallback is explicit."""
    _ = code
    _ = timeout_ms
    return "Error: execute_python requires a live chat client runtime and cannot run server-side"


def build_tool():
    """Build the LangChain tool instance."""
    return TOOL.build_tool(func=execute)
