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
