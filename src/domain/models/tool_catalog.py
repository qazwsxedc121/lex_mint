"""API models for tool catalog responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolCatalogItem(BaseModel):
    """One tool definition exposed to API clients."""

    name: str = Field(
        ..., description="Stable tool name used for function calling and settings storage"
    )
    description: str = Field(..., description="Backend tool description sent to the model")
    group: str = Field(..., description="UI grouping key")
    source: str = Field(..., description="Tool provider/source identifier")
    enabled_by_default: bool = Field(
        ..., description="Whether the tool is enabled by default in project settings"
    )
    title_i18n_key: str = Field(..., description="Frontend i18n key for the tool title")
    description_i18n_key: str = Field(..., description="Frontend i18n key for the tool description")
    requires_project_knowledge: bool = Field(
        default=False,
        description="Whether the tool requires project knowledge bases to be usable",
    )
    plugin_id: str | None = Field(default=None, description="Owning plugin id")
    plugin_name: str | None = Field(default=None, description="Owning plugin display name")
    plugin_version: str | None = Field(default=None, description="Owning plugin version")


class ToolCatalogGroup(BaseModel):
    """A group of tool definitions for UI rendering."""

    key: str = Field(..., description="Stable group key")
    title_i18n_key: str = Field(..., description="Frontend i18n key for the group title")
    description_i18n_key: str = Field(
        ..., description="Frontend i18n key for the group description"
    )
    tools: list[ToolCatalogItem] = Field(default_factory=list)


class ToolCatalogResponse(BaseModel):
    """Complete tool catalog payload."""

    groups: list[ToolCatalogGroup] = Field(default_factory=list)
    tools: list[ToolCatalogItem] = Field(default_factory=list)
