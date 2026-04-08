"""Request-scoped tool metadata plugin entrypoint."""

from __future__ import annotations

from src.tools.request_scoped import REQUEST_SCOPED_TOOL_DEFINITIONS

from .models import ToolPluginContribution


def register() -> ToolPluginContribution:
    return ToolPluginContribution(definitions=list(REQUEST_SCOPED_TOOL_DEFINITIONS))
