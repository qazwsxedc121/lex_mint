"""Shared dependency providers for FastAPI routers and service composition."""

from __future__ import annotations

from typing import Optional

from .config import settings
from src.application.chat import (
    ChatApplicationService,
    build_default_chat_application_service,
)
from src.infrastructure.config.assistant_config_service import AssistantConfigService
from src.infrastructure.config.model_config_service import ModelConfigService
from src.infrastructure.config.project_service import ProjectService
from src.infrastructure.files.file_service import FileService
from src.infrastructure.storage.conversation_storage import (
    ConversationStorage,
    create_storage_with_project_resolver,
)
from .services.project_workspace_state_service import ProjectWorkspaceStateService

_model_service: Optional[ModelConfigService] = None
_assistant_service: Optional[AssistantConfigService] = None
_project_service: Optional[ProjectService] = None
_project_workspace_state_service: Optional[ProjectWorkspaceStateService] = None
_storage: Optional[ConversationStorage] = None
_file_service: Optional[FileService] = None
_chat_application_service: Optional[ChatApplicationService] = None


def get_model_service() -> ModelConfigService:
    global _model_service
    if _model_service is None:
        _model_service = ModelConfigService()
    return _model_service


def get_assistant_service() -> AssistantConfigService:
    global _assistant_service
    if _assistant_service is None:
        _assistant_service = AssistantConfigService(model_service=get_model_service())
    return _assistant_service


def get_project_service() -> ProjectService:
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service


def get_project_workspace_state_service() -> ProjectWorkspaceStateService:
    global _project_workspace_state_service
    if _project_workspace_state_service is None:
        _project_workspace_state_service = ProjectWorkspaceStateService(get_project_service())
    return _project_workspace_state_service


def get_storage() -> ConversationStorage:
    global _storage
    if _storage is None:
        _storage = create_storage_with_project_resolver(
            settings.conversations_dir,
            project_service=get_project_service(),
            assistant_service=get_assistant_service(),
            model_service=get_model_service(),
        )
    return _storage


def get_file_service() -> FileService:
    global _file_service
    if _file_service is None:
        _file_service = FileService(settings.attachments_dir, settings.max_file_size_mb)
    return _file_service


def get_chat_application_service() -> ChatApplicationService:
    global _chat_application_service
    if _chat_application_service is None:
        _chat_application_service = build_default_chat_application_service(
            storage=get_storage(),
            file_service=get_file_service(),
        )
    return _chat_application_service
