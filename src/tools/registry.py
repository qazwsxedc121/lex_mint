"""
Tool Registry - defines and manages tools for LLM function calling.

Tools are defined using LangChain's @tool decorator so they work natively
with bind_tools() across all LLM providers.
"""

import ast
import operator
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from langchain_core.tools import tool, BaseTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@tool
def get_current_time(timezone_name: str = "UTC") -> str:
    """Get the current date and time in the specified timezone.

    Args:
        timezone_name: Timezone name. Supports "UTC" and UTC offset format
            like "UTC+8", "UTC-5". Defaults to "UTC".

    Returns:
        Current date and time as a formatted string.
    """
    try:
        if timezone_name.upper() == "UTC":
            tz = timezone.utc
        elif timezone_name.upper().startswith("UTC"):
            offset_str = timezone_name[3:]
            offset_hours = int(offset_str)
            tz = timezone(timedelta(hours=offset_hours))
        else:
            # Fallback: try as UTC offset number
            tz = timezone.utc
        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
    except Exception as e:
        return f"Error getting time: {e}"


# Safe operator mapping for calculator
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_expr(node: ast.AST) -> float:
    """Recursively evaluate an AST expression using only safe operators."""
    if isinstance(node, ast.Expression):
        return _safe_eval_expr(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left = _safe_eval_expr(node.left)
        right = _safe_eval_expr(node.right)
        return op_func(left, right)
    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(_safe_eval_expr(node.operand))
    raise ValueError(f"Unsupported expression type: {type(node).__name__}")


@tool
def simple_calculator(expression: str) -> str:
    """Evaluate a basic mathematical expression.

    Supports: +, -, *, /, //, %, ** and parentheses.
    Only numeric literals and arithmetic operators are allowed (no variables or functions).

    Args:
        expression: A math expression string, e.g. "1234 * 5678" or "(2 + 3) ** 4".

    Returns:
        The result of the calculation as a string.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval_expr(tree)
        # Format: avoid trailing .0 for integer results
        if isinstance(result, float) and result == int(result) and abs(result) < 1e15:
            return str(int(result))
        return str(result)
    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self) -> None:
        self._tools: List[BaseTool] = [
            get_current_time,
            simple_calculator,
        ]
        self._tool_map = {t.name: t for t in self._tools}

    def get_all_tools(self) -> List[BaseTool]:
        """Return all registered tool objects (for bind_tools)."""
        return list(self._tools)

    def get_tool_by_name(self, name: str) -> Optional[BaseTool]:
        """Look up a tool by name."""
        return self._tool_map.get(name)

    def execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool by name with the given arguments.

        Args:
            name: Tool name.
            args: Argument dict matching the tool's schema.

        Returns:
            Tool result as a string.
        """
        tool_obj = self._tool_map.get(name)
        if tool_obj is None:
            return f"Error: Unknown tool '{name}'"
        try:
            result = tool_obj.invoke(args)
            return str(result)
        except Exception as e:
            logger.error(f"Tool execution error ({name}): {e}", exc_info=True)
            return f"Error executing {name}: {e}"


# Module-level singleton
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global ToolRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
