"""Builtin tool: simple_calculator."""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable

from pydantic import BaseModel, Field

from ..definitions import ToolDefinition


class SimpleCalculatorArgs(BaseModel):
    """Arguments for simple_calculator."""

    expression: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Arithmetic expression using numbers, parentheses, and + - * / // % **.",
    )


TOOL = ToolDefinition(
    name="simple_calculator",
    description="Evaluate a numeric arithmetic expression using safe operators only.",
    args_schema=SimpleCalculatorArgs,
    group="builtin",
    source="builtin",
    enabled_by_default=False,
)


_SAFE_OPERATORS: dict[type[ast.operator] | type[ast.unaryop], Callable[..., float]] = {
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
    if isinstance(node, ast.Expression):
        return _safe_eval_expr(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left = _safe_eval_expr(node.left)
        right = _safe_eval_expr(node.right)
        return float(op_func(left, right))
    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return float(op_func(_safe_eval_expr(node.operand)))
    raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def execute(*, expression: str) -> str:
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


def build_tool():
    """Build the LangChain tool instance."""
    return TOOL.build_tool(func=execute)
