"""Web tool metadata plugin entrypoint."""

from __future__ import annotations

from src.tools.request_scoped import READ_WEBPAGE_TOOL, WEB_SEARCH_TOOL

from .models import ToolPluginContribution


def register() -> ToolPluginContribution:
    return ToolPluginContribution(definitions=[WEB_SEARCH_TOOL, READ_WEBPAGE_TOOL])
