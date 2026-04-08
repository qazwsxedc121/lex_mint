"""Knowledge tool metadata plugin entrypoint."""

from __future__ import annotations

from src.tools.request_scoped import READ_KNOWLEDGE_TOOL, SEARCH_KNOWLEDGE_TOOL

from .models import ToolPluginContribution


def register() -> ToolPluginContribution:
    return ToolPluginContribution(definitions=[SEARCH_KNOWLEDGE_TOOL, READ_KNOWLEDGE_TOOL])
