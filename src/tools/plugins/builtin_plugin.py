"""Builtin tools plugin entrypoint."""

from __future__ import annotations

from src.tools.builtin import (
    BUILTIN_TOOL_DEFINITIONS,
    build_builtin_tools,
    get_builtin_tool_handler,
)

from .models import ToolPluginContribution


def register() -> ToolPluginContribution:
    handlers = {}
    for definition in BUILTIN_TOOL_DEFINITIONS:
        handler = get_builtin_tool_handler(definition.name)
        if handler is not None:
            handlers[definition.name] = handler
    return ToolPluginContribution(
        definitions=list(BUILTIN_TOOL_DEFINITIONS),
        tools=build_builtin_tools(),
        tool_handlers=handlers,
    )
