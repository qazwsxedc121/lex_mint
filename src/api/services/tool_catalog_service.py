"""Build a unified tool catalog for API and UI consumers."""

from __future__ import annotations

from typing import Dict, List

from src.tools.definitions import ToolDefinition
from src.tools.registry import get_tool_registry
from src.tools.request_scoped import REQUEST_SCOPED_TOOL_DEFINITIONS

from ..models.tool_catalog import ToolCatalogGroup, ToolCatalogItem, ToolCatalogResponse


class ToolCatalogService:
    """Aggregates builtin and request-scoped tool definitions into one catalog."""

    GROUP_ORDER = ["builtin", "projectDocuments", "knowledge"]

    @classmethod
    def get_tool_definitions(cls) -> List[ToolDefinition]:
        registry = get_tool_registry()
        definitions = list(registry.get_all_definitions())
        definitions.extend(REQUEST_SCOPED_TOOL_DEFINITIONS)

        seen_names = set()
        unique_definitions: List[ToolDefinition] = []
        for definition in definitions:
            if definition.name in seen_names:
                continue
            seen_names.add(definition.name)
            unique_definitions.append(definition)
        return unique_definitions

    @classmethod
    def build_catalog(cls) -> ToolCatalogResponse:
        definitions = cls.get_tool_definitions()
        items = [cls._to_item(definition) for definition in definitions]

        grouped: Dict[str, List[ToolCatalogItem]] = {group: [] for group in cls.GROUP_ORDER}
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
    def _to_item(definition: ToolDefinition) -> ToolCatalogItem:
        return ToolCatalogItem(
            name=definition.name,
            description=definition.description,
            group=definition.group,
            source=definition.source,
            enabled_by_default=definition.enabled_by_default,
            title_i18n_key=definition.title_i18n_key,
            description_i18n_key=definition.description_i18n_key,
            requires_project_knowledge=definition.requires_project_knowledge,
        )
