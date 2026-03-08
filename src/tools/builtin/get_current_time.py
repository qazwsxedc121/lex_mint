"""Builtin tool: get_current_time."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from ..definitions import ToolDefinition


class GetCurrentTimeArgs(BaseModel):
    """Arguments for get_current_time."""

    timezone_name: str = Field(
        default="UTC",
        description=(
            "IANA timezone like Asia/Shanghai, UTC, or UTC offset like UTC+8 or UTC-05:00."
        ),
    )


TOOL = ToolDefinition(
    name="get_current_time",
    description="Return the current date and time for a UTC offset or an IANA timezone.",
    args_schema=GetCurrentTimeArgs,
    group="builtin",
    source="builtin",
    enabled_by_default=False,
)


def _resolve_timezone(timezone_name: str) -> timezone | ZoneInfo:
    value = (timezone_name or "UTC").strip()
    upper_value = value.upper()
    if upper_value == "UTC":
        return timezone.utc
    if upper_value.startswith("UTC"):
        offset_value = value[3:].strip()
        if not offset_value:
            return timezone.utc
        sign = 1
        if offset_value[0] == "+":
            offset_value = offset_value[1:]
        elif offset_value[0] == "-":
            sign = -1
            offset_value = offset_value[1:]

        hours_text, _, minutes_text = offset_value.partition(":")
        hours = int(hours_text)
        minutes = int(minutes_text) if minutes_text else 0
        return timezone(sign * timedelta(hours=hours, minutes=minutes))
    return ZoneInfo(value)


def execute(*, timezone_name: str = "UTC") -> str:
    """Return the current time in the requested timezone."""
    try:
        tz = _resolve_timezone(timezone_name)
        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
    except Exception as exc:
        return f"Error getting time: {exc}"


def build_tool():
    """Build the LangChain tool instance."""
    return TOOL.build_tool(func=execute)
