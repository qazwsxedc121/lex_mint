"""Build a unified tool catalog for API and UI consumers."""

from __future__ import annotations

from src.domain.models.tool_catalog import ToolCatalogGroup, ToolCatalogItem, ToolCatalogResponse
from src.tools.definitions import ToolDefinition
from src.tools.registry import get_tool_registry


class ToolCatalogService:
    """Aggregates plugin-provided tool definitions into one catalog."""

    GROUP_ORDER = ["builtin", "web", "projectDocuments", "knowledge"]

    @classmethod
    def get_tool_definitions(cls) -> list[ToolDefinition]:
        registry = get_tool_registry()
        return list(registry.get_all_definitions())

    @classmethod
    def build_catalog(
        cls,
        *,
        description_overrides: dict[str, str] | None = None,
    ) -> ToolCatalogResponse:
        definitions = cls.get_tool_definitions()
        items = [
            cls._to_item(definition, description_overrides=description_overrides)
            for definition in definitions
        ]

        grouped: dict[str, list[ToolCatalogItem]] = {group: [] for group in cls.GROUP_ORDER}
        for item in items:
            grouped.setdefault(item.group, []).append(item)

        groups = [
            ToolCatalogGroup(
                key=group,
                title_i18n_key=f"workspace.settings.toolGroups.{group}.title",
                description_i18n_key=f"workspace.settings.toolGroups.{group}.description",
                tools=grouped.get(group, []),
            )
            for group in cls.GROUP_ORDER
            if grouped.get(group)
        ]
        return ToolCatalogResponse(groups=groups, tools=items)

    @staticmethod
    def _to_item(
        definition: ToolDefinition,
        *,
        description_overrides: dict[str, str] | None = None,
    ) -> ToolCatalogItem:
        effective_description = definition.description
        if description_overrides and definition.name in description_overrides:
            candidate = str(description_overrides[definition.name] or "").strip()
            if candidate:
                effective_description = candidate
        return ToolCatalogItem(
            name=definition.name,
            description=effective_description,
            group=definition.group,
            source=definition.source,
            enabled_by_default=definition.enabled_by_default,
            title_i18n_key=definition.title_i18n_key,
            description_i18n_key=definition.description_i18n_key,
            requires_project_knowledge=definition.requires_project_knowledge,
            plugin_id=definition.plugin_id,
            plugin_name=definition.plugin_name,
            plugin_version=definition.plugin_version,
        )
