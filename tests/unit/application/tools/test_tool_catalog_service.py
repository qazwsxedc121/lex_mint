"""Unit tests for unified tool catalog service."""

from __future__ import annotations

from src.application.tools.tool_catalog_service import ToolCatalogService


def test_build_catalog_includes_all_tool_names():
    catalog = ToolCatalogService.build_catalog()
    tool_names = [tool.name for tool in catalog.tools]

    assert tool_names == [
        "get_current_time",
        "execute_python",
        "execute_javascript",
        "simple_calculator",
        "format_json",
        "text_statistics",
        "web_search",
        "read_webpage",
        "read_project_document",
        "read_current_document",
        "search_project_text",
        "apply_diff_project_document",
        "apply_diff_current_document",
        "search_knowledge",
        "read_knowledge",
    ]


def test_build_catalog_groups_tools_in_ui_order():
    catalog = ToolCatalogService.build_catalog()

    assert [group.key for group in catalog.groups] == [
        "builtin",
        "web",
        "projectDocuments",
        "knowledge",
    ]
    assert [tool.name for tool in catalog.groups[0].tools] == [
        "get_current_time",
        "execute_python",
        "execute_javascript",
        "simple_calculator",
        "format_json",
        "text_statistics",
    ]
    assert [tool.name for tool in catalog.groups[1].tools] == [
        "web_search",
        "read_webpage",
    ]
    assert catalog.groups[0].title_i18n_key == "workspace.settings.toolGroups.builtin.title"
    assert (
        catalog.groups[0].description_i18n_key
        == "workspace.settings.toolGroups.builtin.description"
    )
    assert catalog.tools[0].title_i18n_key == "workspace.settings.tools.get_current_time.title"
    assert (
        catalog.tools[0].description_i18n_key
        == "workspace.settings.tools.get_current_time.description"
    )


def test_build_catalog_exposes_chat_capability_control_metadata():
    catalog = ToolCatalogService.build_catalog()
    by_id = {item.id: item for item in catalog.chat_capabilities}

    assert "web.search_context" in by_id
    capability = by_id["web.search_context"]
    assert capability.control_type == "toggle"
    assert capability.arg_key == "value"
    assert capability.options == []
