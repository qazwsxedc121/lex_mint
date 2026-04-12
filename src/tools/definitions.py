"""Shared tool definition helpers used across builtin and request-scoped tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

SyncToolHandler = Callable[..., Any]
AsyncToolHandler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ToolDefinition:
    """Declarative tool schema shared by different tool providers."""

    name: str
    description: str
    args_schema: type[BaseModel]
    group: str
    source: str
    enabled_by_default: bool = False
    requires_project_knowledge: bool = False
    plugin_id: str | None = None
    plugin_name: str | None = None
    plugin_version: str | None = None

    @property
    def title_i18n_key(self) -> str:
        return f"workspace.settings.tools.{self.name}.title"

    @property
    def description_i18n_key(self) -> str:
        return f"workspace.settings.tools.{self.name}.description"

    def metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "group": self.group,
            "source": self.source,
            "enabled_by_default": self.enabled_by_default,
            "requires_project_knowledge": self.requires_project_knowledge,
        }
        if self.plugin_id is not None:
            metadata["plugin_id"] = self.plugin_id
        if self.plugin_name is not None:
            metadata["plugin_name"] = self.plugin_name
        if self.plugin_version is not None:
            metadata["plugin_version"] = self.plugin_version
        return metadata

    def build_tool(
        self,
        *,
        func: SyncToolHandler | None = None,
        coroutine: AsyncToolHandler | None = None,
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
