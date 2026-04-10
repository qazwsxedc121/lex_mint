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


class ChatCapabilityItem(BaseModel):
    """One plugin-declared chat input capability."""

    class OptionItem(BaseModel):
        value: str = Field(..., description="Stable option value sent to backend args")
        label_i18n_key: str = Field(..., description="Frontend i18n key for option label")
        description_i18n_key: str | None = Field(
            default=None, description="Optional frontend i18n key for option description"
        )

    id: str = Field(..., description="Stable capability id used in chat requests")
    plugin_id: str = Field(..., description="Owning plugin id")
    plugin_name: str | None = Field(default=None, description="Owning plugin display name")
    plugin_version: str | None = Field(default=None, description="Owning plugin version")
    title_i18n_key: str = Field(..., description="Frontend i18n key for capability title")
    description_i18n_key: str = Field(
        ..., description="Frontend i18n key for capability description"
    )
    icon: str | None = Field(default=None, description="Optional icon key for chat input button")
    control_type: str = Field(
        default="toggle", description="Input control type for this capability: toggle or select"
    )
    arg_key: str = Field(
        default="value", description="Argument key used when sending selected control value"
    )
    options: list[OptionItem] = Field(
        default_factory=list, description="Selectable options for select controls"
    )
    default_value: str | None = Field(
        default=None, description="Default selected value for select controls"
    )
    order: int = Field(default=1000, description="Display order for chat input capability toggles")
    default_enabled: bool = Field(
        default=False, description="Whether capability should be enabled by default in input"
    )
    visible_in_input: bool = Field(
        default=True, description="Whether capability should be shown as input toggle"
    )


class ToolCatalogResponse(BaseModel):
    """Complete tool catalog payload."""

    groups: list[ToolCatalogGroup] = Field(default_factory=list)
    tools: list[ToolCatalogItem] = Field(default_factory=list)
    chat_capabilities: list[ChatCapabilityItem] = Field(default_factory=list)
