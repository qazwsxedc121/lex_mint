"""Utility tools plugin entrypoint."""

from __future__ import annotations

from src.tools.plugins.models import ToolPluginContribution

from .definitions import (
    FORMAT_JSON_TOOL,
    GET_CURRENT_TIME_TOOL,
    SIMPLE_CALCULATOR_TOOL,
    TEXT_STATISTICS_TOOL,
    format_json,
    get_current_time,
    simple_calculator,
    text_statistics,
)


def register_tool() -> ToolPluginContribution:
    return ToolPluginContribution(
        definitions=[
            GET_CURRENT_TIME_TOOL,
            SIMPLE_CALCULATOR_TOOL,
            FORMAT_JSON_TOOL,
            TEXT_STATISTICS_TOOL,
        ],
        tools=[
            GET_CURRENT_TIME_TOOL.build_tool(func=get_current_time),
            SIMPLE_CALCULATOR_TOOL.build_tool(func=simple_calculator),
            FORMAT_JSON_TOOL.build_tool(func=format_json),
            TEXT_STATISTICS_TOOL.build_tool(func=text_statistics),
        ],
        tool_handlers={
            "get_current_time": get_current_time,
            "simple_calculator": simple_calculator,
            "format_json": format_json,
            "text_statistics": text_statistics,
        },
    )
