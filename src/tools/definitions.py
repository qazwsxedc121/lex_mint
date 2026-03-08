"""Shared tool definition helpers used across builtin and request-scoped tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, Type

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel


SyncToolHandler = Callable[..., Any]
AsyncToolHandler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ToolDefinition:
    """Declarative tool schema shared by different tool providers."""

    name: str
    description: str
    args_schema: Type[BaseModel]
    group: str
    source: str
    enabled_by_default: bool = False
    requires_project_knowledge: bool = False

    @property
    def title_i18n_key(self) -> str:
        return f"workspace.settings.tools.{self.name}.title"

    @property
    def description_i18n_key(self) -> str:
        return f"workspace.settings.tools.{self.name}.description"

    def metadata(self) -> Dict[str, Any]:
        return {
            "group": self.group,
            "source": self.source,
            "enabled_by_default": self.enabled_by_default,
            "requires_project_knowledge": self.requires_project_knowledge,
        }

    def build_tool(
        self,
        *,
        func: Optional[SyncToolHandler] = None,
        coroutine: Optional[AsyncToolHandler] = None,
    ) -> BaseTool:
        if func is None and coroutine is None:
            raise ValueError(f"Tool '{self.name}' requires func or coroutine")

        return StructuredTool.from_function(
            func=func,
            coroutine=coroutine,
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
            metadata=self.metadata(),
            tags=[self.group, self.source],
        )
