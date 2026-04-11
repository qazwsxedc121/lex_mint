from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.routers import features as features_router


@pytest.mark.asyncio
async def test_feature_plugins_router_returns_session_export_statuses(monkeypatch):
    monkeypatch.setattr(
        features_router,
        "list_session_export_plugin_statuses",
        lambda: [
            features_router.SessionExportPluginStatusResponse(
                id="session_markdown_export",
                name="Session Markdown Export",
                version="0.1.0",
                entrypoint="plugin.py:register_session_export",
                plugin_dir="plugins/session_markdown_export",
                enabled=False,
                loaded=False,
                error=None,
            )
        ],
    )

    response = await features_router.get_feature_plugins()
    assert len(response.session_export_plugins) == 1
    assert response.session_export_plugins[0].id == "session_markdown_export"


@pytest.mark.asyncio
async def test_feature_plugins_router_raises_http_500_on_failure(monkeypatch):
    monkeypatch.setattr(
        features_router,
        "list_session_export_plugin_statuses",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await features_router.get_feature_plugins()
    assert exc_info.value.status_code == 500
