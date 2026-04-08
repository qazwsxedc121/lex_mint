"""Web tool plugin entrypoint."""

from __future__ import annotations

from src.infrastructure.web.web_tool_service import WebToolService
from src.tools.plugins.web_tools_definitions import READ_WEBPAGE_TOOL, WEB_SEARCH_TOOL

from .models import ToolPluginContribution


def register() -> ToolPluginContribution:
    web_tool_service = WebToolService()
    return ToolPluginContribution(
        definitions=[WEB_SEARCH_TOOL, READ_WEBPAGE_TOOL],
        tools=web_tool_service.get_tools(),
        tool_handlers={
            "web_search": web_tool_service.web_search,
            "read_webpage": web_tool_service.read_webpage,
        },
    )
