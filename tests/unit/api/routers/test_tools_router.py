"""Tests for tools router endpoints."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.api.routers import tools as router


@pytest.mark.asyncio
async def test_get_tool_descriptions(monkeypatch):
    monkeypatch.setattr(
        router,
        "ToolDescriptionConfigService",
        lambda: SimpleNamespace(
            default_descriptions={"execute_python": "default description"},
            config=SimpleNamespace(overrides={"execute_python": "override description"}),
            get_effective_description_map=lambda: {"execute_python": "override description"},
        ),
    )
    monkeypatch.setattr(
        router.ToolCatalogService,
        "build_catalog",
        lambda **_kwargs: SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="execute_python",
                    group="builtin",
                    source="builtin",
                    plugin_id="builtin_tools",
                    plugin_name="Builtin Tools",
                    plugin_version="1.0.0",
                    description="override description",
                    title_i18n_key="workspace.settings.tools.execute_python.title",
                    description_i18n_key="workspace.settings.tools.execute_python.description",
                )
            ]
        ),
    )

    response = await router.get_tool_descriptions()
    assert len(response.tools) == 1
    item = response.tools[0]
    assert item.name == "execute_python"
    assert item.plugin_id == "builtin_tools"
    assert item.default_description == "default description"
    assert item.override_description == "override description"
    assert item.effective_description == "override description"


@pytest.mark.asyncio
async def test_update_tool_descriptions(monkeypatch):
    mock_service = Mock()
    mock_service.save_overrides = Mock()
    monkeypatch.setattr(router, "ToolDescriptionConfigService", lambda: mock_service)

    response = await router.update_tool_descriptions(
        router.ToolDescriptionsUpdate(overrides={"execute_python": "custom guidance"})
    )
    assert response["message"] == "Configuration updated successfully"
    mock_service.save_overrides.assert_called_once_with({"execute_python": "custom guidance"})


@pytest.mark.asyncio
async def test_get_tool_plugins(monkeypatch):
    monkeypatch.setattr(
        router,
        "get_tool_registry",
        lambda: SimpleNamespace(
            get_plugin_statuses=lambda: [
                SimpleNamespace(
                    id="builtin_tools",
                    name="Builtin Tools",
                    version="1.0.0",
                    entrypoint="src.tools.plugins.builtin_plugin:register",
                    plugin_dir="D:/work/pythonProjects/lex_mint/tool_plugins/builtin_tools",
                    enabled=True,
                    loaded=True,
                    definitions_count=6,
                    tools_count=6,
                    error=None,
                )
            ]
        ),
    )

    response = await router.get_tool_plugins()
    assert len(response.plugins) == 1
    item = response.plugins[0]
    assert item.id == "builtin_tools"
    assert item.loaded is True
    assert item.definitions_count == 6
