"""Project document tool metadata plugin entrypoint."""

from __future__ import annotations

from src.tools.request_scoped import (
    APPLY_DIFF_CURRENT_DOCUMENT_TOOL,
    APPLY_DIFF_PROJECT_DOCUMENT_TOOL,
    READ_CURRENT_DOCUMENT_TOOL,
    READ_PROJECT_DOCUMENT_TOOL,
    SEARCH_PROJECT_TEXT_TOOL,
)

from .models import ToolPluginContribution


def register() -> ToolPluginContribution:
    return ToolPluginContribution(
        definitions=[
            READ_PROJECT_DOCUMENT_TOOL,
            READ_CURRENT_DOCUMENT_TOOL,
            SEARCH_PROJECT_TEXT_TOOL,
            APPLY_DIFF_PROJECT_DOCUMENT_TOOL,
            APPLY_DIFF_CURRENT_DOCUMENT_TOOL,
        ]
    )
