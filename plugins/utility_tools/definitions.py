"""Tool definitions and implementations for utility tools plugin."""

from __future__ import annotations

import ast
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from src.tools.definitions import ToolDefinition


class GetCurrentTimeArgs(BaseModel):
    """Arguments for get_current_time."""

    timezone_name: str = Field(
        default="UTC",
        description=(
            "IANA timezone like Asia/Shanghai, UTC, or UTC offset like UTC+8 or UTC-05:00."
        ),
    )


GET_CURRENT_TIME_TOOL = ToolDefinition(
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


def get_current_time(*, timezone_name: str = "UTC") -> str:
    """Return the current time in the requested timezone."""
    try:
        tz = _resolve_timezone(timezone_name)
        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
    except Exception as exc:
        return f"Error getting time: {exc}"


class SimpleCalculatorArgs(BaseModel):
    """Arguments for simple_calculator."""

    expression: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Arithmetic expression using numbers, parentheses, and + - * / // % **.",
    )


SIMPLE_CALCULATOR_TOOL = ToolDefinition(
    name="simple_calculator",
    description="Evaluate a numeric arithmetic expression using safe operators only.",
    args_schema=SimpleCalculatorArgs,
    group="builtin",
    source="builtin",
    enabled_by_default=False,
)


_SAFE_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
    ast.FloorDiv: lambda left, right: left // right,
    ast.Mod: lambda left, right: left % right,
    ast.Pow: lambda left, right: left**right,
}

_SAFE_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.USub: lambda value: -value,
    ast.UAdd: lambda value: value,
}


def _safe_eval_expr(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval_expr(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_BINARY_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left = _safe_eval_expr(node.left)
        right = _safe_eval_expr(node.right)
        return float(op_func(left, right))
    if isinstance(node, ast.UnaryOp):
        unary_op_func = _SAFE_UNARY_OPERATORS.get(type(node.op))
        if unary_op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return float(unary_op_func(_safe_eval_expr(node.operand)))
    raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def simple_calculator(*, expression: str) -> str:
    """Evaluate a numeric arithmetic expression safely."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval_expr(tree)
        if isinstance(result, float) and result == int(result) and abs(result) < 1e15:
            return str(int(result))
        return str(result)
    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as exc:
        return f"Error: {exc}"


class FormatJsonArgs(BaseModel):
    """Arguments for format_json."""

    value: str = Field(
        ...,
        min_length=1,
        description="JSON string to validate and format.",
    )
    indent: int = Field(
        default=2,
        ge=0,
        le=8,
        description="Indent width used when pretty-printing the JSON payload.",
    )
    sort_keys: bool = Field(
        default=False,
        description="Whether to sort object keys alphabetically in the formatted result.",
    )


FORMAT_JSON_TOOL = ToolDefinition(
    name="format_json",
    description="Validate and format a JSON string for inspection or reuse.",
    args_schema=FormatJsonArgs,
    group="builtin",
    source="builtin",
    enabled_by_default=False,
)


def format_json(*, value: str, indent: int = 2, sort_keys: bool = False) -> str:
    """Validate and pretty-print JSON content."""
    try:
        parsed = json.loads(value)
        separators = (",", ":") if indent == 0 else None
        return json.dumps(
            parsed,
            ensure_ascii=False,
            indent=indent or None,
            sort_keys=sort_keys,
            separators=separators,
        )
    except Exception as exc:
        return f"Error: Invalid JSON - {exc}"


class TextStatisticsArgs(BaseModel):
    """Arguments for text_statistics."""

    text: str = Field(
        ...,
        description="Text to analyze for length and token-like counts.",
    )


TEXT_STATISTICS_TOOL = ToolDefinition(
    name="text_statistics",
    description="Count characters, words, lines, and UTF-8 bytes for a text payload.",
    args_schema=TextStatisticsArgs,
    group="builtin",
    source="builtin",
    enabled_by_default=False,
)


def text_statistics(*, text: str) -> str:
    """Return basic statistics about a piece of text."""
    lines = text.splitlines()
    words = [part for part in text.split() if part]
    payload = {
        "chars": len(text),
        "chars_no_whitespace": sum(1 for char in text if not char.isspace()),
        "words": len(words),
        "lines": len(lines) if lines else (1 if text else 0),
        "utf8_bytes": len(text.encode("utf-8")),
    }
    return json.dumps(payload, ensure_ascii=False)
