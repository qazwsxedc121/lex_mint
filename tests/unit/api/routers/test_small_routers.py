"""Coverage-oriented tests for smaller API routers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from edge_tts.exceptions import NoAudioReceived

from src.api.routers import folders as folders_router
from src.api.routers import followup as followup_router
from src.api.routers import search_config as search_config_router
from src.api.routers import title_generation as title_router
from src.api.routers import tools as tools_router
from src.api.routers import tts as tts_router
from src.infrastructure.config.folder_service import Folder


@pytest.mark.asyncio
async def test_folders_router_success_and_error_paths():
    service = Mock()
    storage = Mock()
    folder = Folder(id="folder-1", name="Inbox", order=0)

    service.list_folders = AsyncMock(return_value=[folder])
    service.create_folder = AsyncMock(return_value=folder)
    service.update_folder = AsyncMock(return_value=folder)
    service.delete_folder = AsyncMock()
    service.reorder_folder = AsyncMock(return_value=folder)
    storage.list_sessions = AsyncMock(
        return_value=[
            {"session_id": "s1", "folder_id": "folder-1"},
            {"session_id": "s2", "folder_id": "folder-1"},
            {"session_id": "s3", "folder_id": None},
        ]
    )
    storage.update_session_folder = AsyncMock(side_effect=[None, RuntimeError("clear failed")])

    assert (await folders_router.list_folders(service=service))[0].id == "folder-1"  # type: ignore[arg-type]
    assert (await folders_router.create_folder(folders_router.CreateFolderRequest(name="Inbox"), service=service)).id == "folder-1"  # type: ignore[arg-type]
    assert (
        await folders_router.update_folder(
            "folder-1",
            folders_router.UpdateFolderRequest(name="Inbox"),
            service=service,  # type: ignore[arg-type]
        )
    ).name == "Inbox"

    await folders_router.delete_folder("folder-1", service=service, storage=storage)  # type: ignore[arg-type]
    storage.update_session_folder.assert_any_await(session_id="s1", folder_id=None, context_type="chat")
    storage.update_session_folder.assert_any_await(session_id="s2", folder_id=None, context_type="chat")
    service.delete_folder.assert_awaited_once_with("folder-1")

    reordered = await folders_router.reorder_folder(
        "folder-1",
        folders_router.ReorderFolderRequest(order=2),
        service=service,  # type: ignore[arg-type]
    )
    assert reordered.order == 0

    service.list_folders = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(HTTPException) as exc_info:
        await folders_router.list_folders(service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 500

    service.update_folder = AsyncMock(side_effect=ValueError("missing"))
    with pytest.raises(HTTPException) as exc_info:
        await folders_router.update_folder(
            "missing",
            folders_router.UpdateFolderRequest(name="x"),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    service.delete_folder = AsyncMock(side_effect=ValueError("missing"))
    with pytest.raises(HTTPException) as exc_info:
        await folders_router.delete_folder("missing", service=service, storage=storage)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404

    service.reorder_folder = AsyncMock(side_effect=ValueError("folder not found"))
    with pytest.raises(HTTPException) as exc_info:
        await folders_router.reorder_folder(
            "missing",
            folders_router.ReorderFolderRequest(order=1),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    service.reorder_folder = AsyncMock(side_effect=ValueError("invalid order"))
    with pytest.raises(HTTPException) as exc_info:
        await folders_router.reorder_folder(
            "folder-1",
            folders_router.ReorderFolderRequest(order=-1),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_followup_router_paths():
    config = SimpleNamespace(
        enabled=True,
        count=3,
        model_id="model-1",
        max_context_rounds=4,
        timeout_seconds=20,
        prompt_template="prompt",
    )
    service = Mock(config=config)
    service.save_config = Mock()
    service.generate_followups_async = AsyncMock(return_value=["q1", "q2"])
    storage = Mock()
    storage.get_session = AsyncMock(return_value={"state": {"messages": [{"role": "user", "content": "hi"}]}})

    response = await followup_router.get_config(service=service)  # type: ignore[arg-type]
    assert response.model_id == "model-1"

    updated = await followup_router.update_config(
        followup_router.FollowupConfigUpdate(enabled=False, count=1),
        service=service,  # type: ignore[arg-type]
    )
    assert updated["message"] == "Configuration updated successfully"
    service.save_config.assert_called_once_with({"enabled": False, "count": 1})

    generated = await followup_router.generate_followups(
        session_id="session-1",
        context_type="chat",
        project_id=None,
        service=service,  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
    )
    assert generated["questions"] == ["q1", "q2"]

    storage.get_session = AsyncMock(return_value={"state": {"messages": []}})
    empty = await followup_router.generate_followups(
        session_id="session-1",
        context_type="chat",
        project_id=None,
        service=service,  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
    )
    assert empty["questions"] == []

    with pytest.raises(HTTPException) as exc_info:
        await followup_router.update_config(
            followup_router.FollowupConfigUpdate(),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    broken_service = Mock()
    broken_service.config = property(lambda self: None)  # pragma: no cover
    broken_service.save_config = Mock(side_effect=RuntimeError("save failed"))
    broken_storage = Mock()
    broken_storage.get_session = AsyncMock(side_effect=FileNotFoundError())

    class _BrokenConfigService:
        @property
        def config(self):
            raise RuntimeError("config failed")

    with pytest.raises(HTTPException) as exc_info:
        await followup_router.get_config(service=_BrokenConfigService())  # type: ignore[arg-type]
    assert exc_info.value.status_code == 500

    with pytest.raises(HTTPException) as exc_info:
        await followup_router.update_config(
            followup_router.FollowupConfigUpdate(enabled=True),
            service=broken_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 500

    with pytest.raises(HTTPException) as exc_info:
        await followup_router.generate_followups(
            session_id="missing",
            context_type="chat",
            project_id=None,
            service=service,  # type: ignore[arg-type]
            storage=broken_storage,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    broken_storage.get_session = AsyncMock(return_value={"state": {"messages": [{"role": "user", "content": "x"}]}})
    service.generate_followups_async = AsyncMock(side_effect=RuntimeError("generate failed"))
    with pytest.raises(HTTPException) as exc_info:
        await followup_router.generate_followups(
            session_id="session-1",
            context_type="chat",
            project_id=None,
            service=service,  # type: ignore[arg-type]
            storage=broken_storage,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_title_generation_router_paths():
    config = SimpleNamespace(
        enabled=True,
        trigger_threshold=2,
        model_id="model-1",
        prompt_template="prompt",
        max_context_rounds=3,
        timeout_seconds=15,
    )
    service = Mock(config=config)
    service.save_config = Mock()
    service.generate_title_async = AsyncMock(return_value="A title")

    response = await title_router.get_config(service=service)  # type: ignore[arg-type]
    assert response.trigger_threshold == 2

    updated = await title_router.update_config(
        title_router.TitleGenerationConfigUpdate(enabled=False),
        service=service,  # type: ignore[arg-type]
    )
    assert updated["message"] == "Configuration updated successfully"

    generated = await title_router.generate_title(
        title_router.ManualGenerateRequest(session_id="session-1"),
        service=service,  # type: ignore[arg-type]
    )
    assert generated["title"] == "A title"

    with pytest.raises(HTTPException) as exc_info:
        await title_router.update_config(
            title_router.TitleGenerationConfigUpdate(),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    class _BrokenTitleService:
        @property
        def config(self):
            raise RuntimeError("config failed")

    with pytest.raises(HTTPException) as exc_info:
        await title_router.get_config(service=_BrokenTitleService())  # type: ignore[arg-type]
    assert exc_info.value.status_code == 500

    failing_save = Mock(config=config)
    failing_save.save_config = Mock(side_effect=RuntimeError("save failed"))
    with pytest.raises(HTTPException) as exc_info:
        await title_router.update_config(
            title_router.TitleGenerationConfigUpdate(enabled=True),
            service=failing_save,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 500

    no_title_service = Mock(config=config)
    no_title_service.generate_title_async = AsyncMock(return_value="")
    with pytest.raises(HTTPException) as exc_info:
        await title_router.generate_title(
            title_router.ManualGenerateRequest(session_id="session-1"),
            service=no_title_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 500

    error_service = Mock(config=config)
    error_service.generate_title_async = AsyncMock(side_effect=RuntimeError("generate failed"))
    with pytest.raises(HTTPException) as exc_info:
        await title_router.generate_title(
            title_router.ManualGenerateRequest(session_id="session-1"),
            service=error_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_tts_router_paths(monkeypatch):
    config_service = Mock()
    config_service.reload_config = Mock()
    config_service.config = SimpleNamespace(enabled=True)
    fake_tts_service = SimpleNamespace(config_service=config_service, synthesize=AsyncMock(return_value=b"audio"))
    monkeypatch.setattr(tts_router, "tts_service", fake_tts_service)

    response = await tts_router.synthesize(tts_router.TTSSynthesizeRequest(text="hello", voice="voice", rate="+0%"))
    assert response.media_type == "audio/mpeg"
    assert response.body == b"audio"

    with pytest.raises(HTTPException) as exc_info:
        await tts_router.synthesize(tts_router.TTSSynthesizeRequest(text="   "))
    assert exc_info.value.status_code == 400

    config_service.config = SimpleNamespace(enabled=False)
    with pytest.raises(HTTPException) as exc_info:
        await tts_router.synthesize(tts_router.TTSSynthesizeRequest(text="hello"))
    assert exc_info.value.status_code == 403

    config_service.config = SimpleNamespace(enabled=True)
    fake_tts_service.synthesize = AsyncMock(side_effect=NoAudioReceived())
    with pytest.raises(HTTPException) as exc_info:
        await tts_router.synthesize(tts_router.TTSSynthesizeRequest(text="hello"))
    assert exc_info.value.status_code == 422

    fake_tts_service.synthesize = AsyncMock(side_effect=ValueError("bad input"))
    with pytest.raises(HTTPException) as exc_info:
        await tts_router.synthesize(tts_router.TTSSynthesizeRequest(text="hello"))
    assert exc_info.value.status_code == 400

    fake_tts_service.synthesize = AsyncMock(side_effect=RuntimeError("tts failed"))
    with pytest.raises(HTTPException) as exc_info:
        await tts_router.synthesize(tts_router.TTSSynthesizeRequest(text="hello"))
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_search_config_and_tools_router_paths(monkeypatch):
    service = Mock()
    service.config = SimpleNamespace(provider="duckduckgo", max_results=5, timeout_seconds=10)
    service.save_config = Mock()

    response = await search_config_router.get_config(service=service)  # type: ignore[arg-type]
    assert response.provider == "duckduckgo"

    updated = await search_config_router.update_config(
        search_config_router.SearchConfigUpdate(provider="tavily", max_results=3),
        service=service,  # type: ignore[arg-type]
    )
    assert updated["message"] == "Configuration updated successfully"
    service.save_config.assert_called_once_with({"provider": "tavily", "max_results": 3})

    with pytest.raises(HTTPException) as exc_info:
        await search_config_router.update_config(
            search_config_router.SearchConfigUpdate(),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await search_config_router.update_config(
            search_config_router.SearchConfigUpdate(provider="google"),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    class _BrokenSearchService:
        @property
        def config(self):
            raise RuntimeError("config failed")

    with pytest.raises(HTTPException) as exc_info:
        await search_config_router.get_config(service=_BrokenSearchService())  # type: ignore[arg-type]
    assert exc_info.value.status_code == 500

    failing_service = Mock()
    failing_service.config = service.config
    failing_service.save_config = Mock(side_effect=RuntimeError("save failed"))
    with pytest.raises(HTTPException) as exc_info:
        await search_config_router.update_config(
            search_config_router.SearchConfigUpdate(provider="duckduckgo"),
            service=failing_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 500

    monkeypatch.setattr(tools_router.ToolCatalogService, "build_catalog", lambda: {"builtin_tools": [], "request_scoped_tools": []})
    assert (await tools_router.get_tool_catalog())["builtin_tools"] == []

    monkeypatch.setattr(tools_router.ToolCatalogService, "build_catalog", lambda: (_ for _ in ()).throw(RuntimeError("catalog failed")))
    with pytest.raises(HTTPException) as exc_info:
        await tools_router.get_tool_catalog()
    assert exc_info.value.status_code == 500
