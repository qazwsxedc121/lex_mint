"""Builtin tools plugin entrypoint."""

from __future__ import annotations

from src.tools.builtin import (
    BUILTIN_TOOL_DEFINITIONS,
    build_builtin_tools,
    get_builtin_tool_handler,
)
from src.tools.plugins.models import ToolPluginContribution
from src.tools.request_scoped import (
    APPLY_DIFF_CURRENT_DOCUMENT_TOOL,
    APPLY_DIFF_PROJECT_DOCUMENT_TOOL,
    READ_CURRENT_DOCUMENT_TOOL,
    READ_KNOWLEDGE_TOOL,
    READ_PROJECT_DOCUMENT_TOOL,
    SEARCH_KNOWLEDGE_TOOL,
    SEARCH_PROJECT_TEXT_TOOL,
)


def register_tool() -> ToolPluginContribution:
    handlers = {}
    for definition in BUILTIN_TOOL_DEFINITIONS:
        handler = get_builtin_tool_handler(definition.name)
        if handler is not None:
            handlers[definition.name] = handler
    definitions = list(BUILTIN_TOOL_DEFINITIONS) + [
        READ_PROJECT_DOCUMENT_TOOL,
        READ_CURRENT_DOCUMENT_TOOL,
        SEARCH_PROJECT_TEXT_TOOL,
        APPLY_DIFF_PROJECT_DOCUMENT_TOOL,
        APPLY_DIFF_CURRENT_DOCUMENT_TOOL,
        SEARCH_KNOWLEDGE_TOOL,
        READ_KNOWLEDGE_TOOL,
    ]
    return ToolPluginContribution(
        definitions=definitions,
        tools=build_builtin_tools(),
        tool_handlers=handlers,
    )
