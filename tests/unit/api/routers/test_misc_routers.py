"""Tests for thin API routers with fake services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import HTTPException

from src.api.routers import assistants as assistants_router
from src.api.routers import file_reference_config as file_reference_router
from src.api.routers import folders as folders_router
from src.api.routers import followup as followup_router
from src.api.routers import prompt_templates as templates_router
from src.api.routers import search_config as search_router
from src.api.routers import title_generation as title_router
from src.api.routers import tools as tools_router
from src.api.routers import translation_config as translation_router
from src.api.routers import tts_config as tts_router
from src.api.routers import webpage_config as webpage_router
from src.domain.models.assistant_config import Assistant
from src.domain.models.prompt_template import PromptTemplate
from src.domain.models.tool_catalog import ToolCatalogResponse
from src.infrastructure.config.folder_service import Folder


@dataclass
class _BasicConfig:
    enabled: bool = True
    trigger_threshold: int = 2
    model_id: str = "provider:model"
    prompt_template: str = "prompt"
    max_context_rounds: int = 3
    timeout_seconds: int = 10
    provider: str = "duckduckgo"
    max_results: int = 5
    target_language: str = "en"
    input_target_language: str = "auto"
    local_gguf_model_path: str = ""
    local_gguf_n_ctx: int = 2048
    local_gguf_n_threads: int = 4
    local_gguf_n_gpu_layers: int = 0
    local_gguf_max_tokens: int = 512
    temperature: float = 0.2
    voice: str = "en-US"
    voice_zh: str = "zh-CN"
    rate: str = "+0%"
    volume: str = "+0%"
    max_text_length: int = 1000
    max_urls: int = 3
    max_bytes: int = 100000
    max_content_chars: int = 10000
    user_agent: str = "agent"
    proxy: str | None = None
    trust_env: bool = True
    diagnostics_enabled: bool = False
    diagnostics_timeout_seconds: float = 1.5
    count: int = 3
    ui_preview_max_chars: int = 1200
    ui_preview_max_lines: int = 28
    injection_preview_max_chars: int = 600
    injection_preview_max_lines: int = 40
    chunk_size: int = 2500
    max_chunks: int = 6
    total_budget_chars: int = 10000


class _SaveableService:
    def __init__(self):
        self.config = _BasicConfig()
        self.saved: dict[str, Any] | None = None

    def save_config(self, updates: dict[str, Any]) -> None:
        self.saved = updates


class _AssistantService:
    def __init__(self):
        self.assistant = Assistant(
            id="writer", name="Writer", model_id="openai:gpt", system_prompt="helpful"
        )
        self.calls: list[tuple[str, Any]] = []
        self.fail_with: Exception | None = None

    async def get_assistants(self, *, enabled_only: bool = False):
        self.calls.append(("list", enabled_only))
        return [self.assistant]

    async def get_assistant(self, assistant_id: str):
        self.calls.append(("get", assistant_id))
        if assistant_id == "missing":
            return None
        return self.assistant

    async def add_assistant(self, assistant: Assistant):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(("add", assistant.id))

    async def update_assistant(self, assistant_id: str, assistant: Assistant):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(("update", (assistant_id, assistant.name)))

    async def delete_assistant(self, assistant_id: str):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(("delete", assistant_id))

    async def get_default_assistant_id(self):
        return "writer"

    async def get_default_assistant(self):
        if self.fail_with:
            raise self.fail_with
        return self.assistant

    async def set_default_assistant(self, assistant_id: str):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(("set_default", assistant_id))


class _FolderService:
    def __init__(self):
        self.folder = Folder(id="f1", name="Inbox", order=0)
        self.fail_with: Exception | None = None

    async def list_folders(self):
        return [self.folder]

    async def create_folder(self, name: str):
        if self.fail_with:
            raise self.fail_with
        return Folder(id="f2", name=name, order=1)

    async def update_folder(self, folder_id: str, name: str):
        if self.fail_with:
            raise self.fail_with
        return Folder(id=folder_id, name=name, order=0)

    async def delete_folder(self, folder_id: str):
        if self.fail_with:
            raise self.fail_with

    async def reorder_folder(self, folder_id: str, new_order: int):
        if self.fail_with:
            raise self.fail_with
        return Folder(id=folder_id, name="Inbox", order=new_order)


class _FolderStorage:
    def __init__(self):
        self.updated: list[str] = []

    async def list_sessions(self, context_type: str = "chat"):
        _ = context_type
        return [
            {"session_id": "s1", "folder_id": "f1"},
            {"session_id": "s2", "folder_id": None},
        ]

    async def update_session_folder(
        self, session_id: str, folder_id: str | None, context_type: str = "chat"
    ):
        _ = folder_id, context_type
        self.updated.append(session_id)


class _PromptTemplateService:
    def __init__(self):
        self.template = PromptTemplate(id="tmpl-1", name="Template", content="Hello {name}")
        self.fail_with: Exception | None = None

    async def get_templates(self):
        return [self.template]

    async def get_template(self, template_id: str):
        if template_id == "missing":
            return None
        return self.template

    async def add_template(self, template: PromptTemplate):
        if self.fail_with:
            raise self.fail_with

    async def update_template(self, template_id: str, template: PromptTemplate):
        if self.fail_with:
            raise self.fail_with

    async def delete_template(self, template_id: str):
        if self.fail_with:
            raise self.fail_with


class _FollowupService(_SaveableService):
    async def generate_followups_async(self, messages: list[dict[str, Any]]):
        assert messages
        return ["next question"]


class _SessionStorage:
    async def get_session(self, session_id: str, **kwargs):
        _ = kwargs
        if session_id == "missing":
            raise FileNotFoundError
        return {"state": {"messages": [{"role": "user", "content": "Hello"}]}}


class _TitleService(_SaveableService):
    async def generate_title_async(self, session_id: str):
        return f"title:{session_id}"


@pytest.mark.asyncio
async def test_assistant_router_crud_and_default_routes():
    service = _AssistantService()

    assistants = await assistants_router.list_assistants(service=service)
    assert assistants[0].id == "writer"

    assistant = await assistants_router.get_assistant("writer", service=service)
    assert assistant.name == "Writer"

    created = await assistants_router.create_assistant(
        assistants_router.AssistantCreate(id="critic", name="Critic", model_id="openai:gpt"),
        service=service,
    )
    assert created["id"] == "critic"

    updated = await assistants_router.update_assistant(
        "writer",
        assistants_router.AssistantUpdate(name="Updated"),
        service=service,
    )
    assert updated["message"] == "Assistant updated successfully"

    deleted = await assistants_router.delete_assistant("writer", service=service)
    assert deleted["message"] == "Assistant deleted successfully"

    default_id = await assistants_router.get_default_assistant_id(service=service)
    assert default_id["default_assistant_id"] == "writer"

    default_assistant = await assistants_router.get_default_assistant(service=service)
    assert default_assistant.id == "writer"

    set_default = await assistants_router.set_default_assistant("writer", service=service)
    assert set_default["default_assistant_id"] == "writer"

    with pytest.raises(HTTPException) as exc_info:
        await assistants_router.get_assistant("missing", service=service)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_misc_config_routers_and_tool_catalog(monkeypatch):
    search_service = _SaveableService()
    search_config = await search_router.get_config(service=search_service)
    assert search_config.provider == "duckduckgo"
    update_response = await search_router.update_config(
        updates=search_router.SearchConfigUpdate(provider="tavily", max_results=7),
        service=search_service,
    )
    assert update_response["message"] == "Configuration updated successfully"

    webpage_service = _SaveableService()
    webpage_config = await webpage_router.get_config(service=webpage_service)
    assert webpage_config.max_urls == 3
    assert (
        await webpage_router.update_config(
            updates=webpage_router.WebpageConfigUpdate(max_urls=4),
            service=webpage_service,
        )
    )["message"] == "Configuration updated successfully"

    translation_service = _SaveableService()
    translation_config = await translation_router.get_config(service=translation_service)
    assert translation_config.target_language == "en"
    assert (
        await translation_router.update_config(
            updates=translation_router.TranslationConfigUpdate(provider="local_gguf"),
            service=translation_service,
        )
    )["message"] == "Configuration updated successfully"

    tts_service = _SaveableService()
    tts_config = await tts_router.get_config(service=tts_service)
    assert tts_config.voice == "en-US"
    assert (
        await tts_router.update_config(
            updates=tts_router.TTSConfigUpdate(voice="en-GB"),
            service=tts_service,
        )
    )["message"] == "Configuration updated successfully"
    monkeypatch.setattr(
        tts_router.edge_tts,
        "list_voices",
        lambda: _async_value([{"ShortName": "en-US-A", "Locale": "en-US", "Gender": "Female"}]),
    )
    voices = await tts_router.list_voices()
    assert voices[0].ShortName == "en-US-A"

    file_reference_service = _SaveableService()
    file_reference_config = await file_reference_router.get_config(service=file_reference_service)
    assert file_reference_config.total_budget_chars == 10000
    assert (
        await file_reference_router.update_config(
            updates=file_reference_router.FileReferenceConfigUpdate(total_budget_chars=5000),
            service=file_reference_service,
        )
    )["message"] == "Configuration updated successfully"

    tool_catalog = ToolCatalogResponse(groups=[], tools=[])
    monkeypatch.setattr(
        tools_router.ToolCatalogService, "build_catalog", staticmethod(lambda: tool_catalog)
    )
    assert await tools_router.get_tool_catalog() == tool_catalog


@pytest.mark.asyncio
async def test_followup_title_folder_and_prompt_template_routes(monkeypatch):
    followup_service = _FollowupService()
    followup_config = await followup_router.get_config(service=followup_service)
    assert followup_config.count == 3
    assert (
        await followup_router.update_config(
            updates=followup_router.FollowupConfigUpdate(count=2),
            service=followup_service,
        )
    )["message"] == "Configuration updated successfully"
    generated = await followup_router.generate_followups(
        session_id="session-1",
        service=followup_service,
        storage=_SessionStorage(),
    )
    assert generated["questions"] == ["next question"]

    title_service = _TitleService()
    title_config = await title_router.get_config(service=title_service)
    assert title_config.trigger_threshold == 2
    assert (
        await title_router.update_config(
            updates=title_router.TitleGenerationConfigUpdate(trigger_threshold=3),
            service=title_service,
        )
    )["message"] == "Configuration updated successfully"
    title_generated = await title_router.generate_title(
        request=title_router.ManualGenerateRequest(session_id="session-1"),
        service=title_service,
    )
    assert title_generated["title"] == "title:session-1"

    folder_service = _FolderService()
    folder_storage = _FolderStorage()
    folders = await folders_router.list_folders(service=folder_service)
    assert folders[0].id == "f1"
    created_folder = await folders_router.create_folder(
        request=folders_router.CreateFolderRequest(name="Work"),
        service=folder_service,
    )
    assert created_folder.name == "Work"
    updated_folder = await folders_router.update_folder(
        folder_id="f1",
        request=folders_router.UpdateFolderRequest(name="Inbox 2"),
        service=folder_service,
    )
    assert updated_folder.name == "Inbox 2"
    reordered_folder = await folders_router.reorder_folder(
        folder_id="f1",
        request=folders_router.ReorderFolderRequest(order=2),
        service=folder_service,
    )
    assert reordered_folder.order == 2
    await folders_router.delete_folder(
        folder_id="f1", service=folder_service, storage=folder_storage
    )
    assert folder_storage.updated == ["s1"]

    template_service = _PromptTemplateService()
    templates = await templates_router.list_prompt_templates(service=template_service)
    assert templates[0].id == "tmpl-1"
    created_template = await templates_router.create_prompt_template(
        template_data=templates_router.PromptTemplateCreate(name="Greeter", content="Hi"),
        service=template_service,
    )
    assert created_template["message"] == "Template created successfully"
    template = await templates_router.get_prompt_template("tmpl-1", service=template_service)
    assert template.name == "Template"
    updated_template = await templates_router.update_prompt_template(
        template_id="tmpl-1",
        template_update=templates_router.PromptTemplateUpdate(name="Updated"),
        service=template_service,
    )
    assert updated_template["message"] == "Template updated successfully"
    deleted_template = await templates_router.delete_prompt_template(
        "tmpl-1", service=template_service
    )
    assert deleted_template["message"] == "Template deleted successfully"


@pytest.mark.asyncio
async def test_misc_router_error_mapping():
    service = _AssistantService()
    service.fail_with = ValueError("bad assistant")
    with pytest.raises(HTTPException) as exc_info:
        await assistants_router.create_assistant(
            assistants_router.AssistantCreate(id="x", name="X", model_id="openai:gpt"),
            service=service,
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await search_router.update_config(
            updates=search_router.SearchConfigUpdate(provider="bad"),
            service=_SaveableService(),
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await translation_router.update_config(
            updates=translation_router.TranslationConfigUpdate(provider="bad"),
            service=_SaveableService(),
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await file_reference_router.update_config(
            updates=file_reference_router.FileReferenceConfigUpdate(),
            service=_SaveableService(),
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await followup_router.generate_followups(
            session_id="missing",
            service=_FollowupService(),
            storage=_SessionStorage(),
        )
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await templates_router.get_prompt_template("missing", service=_PromptTemplateService())
    assert exc_info.value.status_code == 404


async def _async_value(value):
    return value
