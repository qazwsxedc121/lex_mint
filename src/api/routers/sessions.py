"""Session management API endpoints."""

import io
import json
import logging
import re
import zipfile
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from src.api.routers.service_protocols import (
    ConversationImportStorageLike,
    ConversationQueryStorageLike,
    SessionApplicationServiceLike,
)
from src.application.chat import SessionApplicationService
from src.application.chat.chatgpt_import_service import ChatGPTImportService
from src.application.chat.markdown_import_service import MarkdownImportService
from src.infrastructure.storage.comparison_storage import ComparisonStorage
from src.infrastructure.storage.conversation_storage import ConversationStorage

from ..dependencies import get_session_application_service as get_shared_session_application_service
from ..dependencies import get_storage as get_shared_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    """创建会话请求"""

    model_id: str | None = None  # 向后兼容
    assistant_id: str | None = None  # 新方式：使用助手
    target_type: Literal["assistant", "model"] | None = None
    temporary: bool = False
    group_assistants: list[str] | None = None  # Group chat: list of assistant IDs
    group_mode: str | None = None  # Group chat mode: "round_robin" | "committee"
    group_settings: dict[str, Any] | None = None  # Structured orchestration settings


class UpdateModelRequest(BaseModel):
    """更新模型请求"""

    model_id: str


class UpdateAssistantRequest(BaseModel):
    """更新助手请求"""

    assistant_id: str


class UpdateTargetRequest(BaseModel):
    """更新会话对话目标请求"""

    target_type: Literal["assistant", "model"]
    assistant_id: str | None = None
    model_id: str | None = None


class UpdateTitleRequest(BaseModel):
    """更新标题请求"""

    title: str


class UpdateParamOverridesRequest(BaseModel):
    """更新参数覆盖请求"""

    param_overrides: dict


class TransferSessionRequest(BaseModel):
    """Move or copy session request."""

    target_context_type: str
    target_project_id: str | None = None


class ImportChatGPTSession(BaseModel):
    """Imported session summary."""

    session_id: str
    title: str
    message_count: int


class ImportChatGPTResponse(BaseModel):
    """ChatGPT import response."""

    imported: int
    skipped: int
    sessions: list[ImportChatGPTSession]
    errors: list[str]


def get_storage() -> ConversationStorage:
    """Dependency injection for ConversationStorage."""
    return get_shared_storage()


def get_session_application_service() -> SessionApplicationService:
    """Dependency injection for session application service."""
    return get_shared_session_application_service()


@router.post("", response_model=dict[str, str])
async def create_session(
    request: CreateSessionRequest | None = None,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """Create a new conversation session.

    Args:
        request: 可选的创建会话请求（包含 assistant_id 或 model_id）
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {"session_id": "uuid-string"}

    Raises:
        400: Invalid context parameters
    """
    # Validate context parameters
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    assistant_id = request.assistant_id if request else None
    model_id = request.model_id if request else None
    target_type = request.target_type if request else None
    temporary = request.temporary if request else False
    group_assistants = request.group_assistants if request else None
    group_mode = request.group_mode if request else None
    group_settings = request.group_settings if request else None
    logger.info(
        f"Creating new session (target_type: {target_type or 'default'}, assistant: {assistant_id or 'default'}, "
        f"model: {model_id or 'default'}, "
        f"temporary: {temporary}, group: {len(group_assistants) if group_assistants else 0}, mode: {group_mode or 'n/a'})..."
    )

    try:
        session_id = await session_service.create_session(
            assistant_id=assistant_id,
            model_id=model_id,
            target_type=target_type,
            temporary=temporary,
            group_assistants=group_assistants,
            group_mode=group_mode,
            group_settings=group_settings,
            context_type=context_type,
            project_id=project_id,
        )
        logger.info(f"✅ 新会话已创建: {session_id}")
        return {"session_id": session_id}
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=dict[str, list[dict]])
async def list_sessions(
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    storage: ConversationQueryStorageLike = Depends(get_storage),
):
    """List all conversation sessions.

    Args:
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {
            "sessions": [
                {
                    "session_id": "uuid",
                    "title": "conversation title",
                    "created_at": "ISO timestamp",
                    "message_count": 10
                },
                ...
            ]
        }

    Raises:
        400: Invalid context parameters
    """
    # Validate context parameters
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info("📋 列出所有会话...")
    try:
        sessions = await storage.list_sessions(context_type=context_type, project_id=project_id)
        logger.info(f"✅ 找到 {len(sessions)} 个会话")
        return {"sessions": sessions}
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search", response_model=dict[str, list[dict]])
async def search_sessions(
    q: str = Query(""),
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    storage: ConversationQueryStorageLike = Depends(get_storage),
):
    """Search sessions by title and message content.

    Args:
        q: Search query string
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {"results": [...]}
    """
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    try:
        results = await storage.search_sessions(q, context_type=context_type, project_id=project_id)
        return {"results": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{session_id}", response_model=dict)
async def get_session(
    session_id: str,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    storage: ConversationQueryStorageLike = Depends(get_storage),
):
    """Get a specific conversation session with full history.

    Args:
        session_id: Session UUID
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {
            "session_id": "uuid",
            "title": "conversation title",
            "created_at": "ISO timestamp",
            "state": {
                "messages": [{"role": "user/assistant", "content": "..."}],
                "current_step": 5
            }
        }

    Raises:
        404: Session not found
        400: Invalid context parameters
    """
    # Validate context parameters
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(f"📂 获取会话: {session_id[:16]}...")
    try:
        session = await storage.get_session(
            session_id, context_type=context_type, project_id=project_id
        )

        # Load comparison data if it exists
        try:
            comparison_storage = ComparisonStorage(storage)
            compare_data = await comparison_storage.load(
                session_id, context_type=context_type, project_id=project_id
            )
            if compare_data:
                session["compare_data"] = compare_data
        except Exception as e:
            logger.warning(f"Failed to load comparison data: {e}")

        msg_count = len(session.get("state", {}).get("messages", []))
        logger.info(f"✅ 会话加载成功，包含 {msg_count} 条消息")
        return session
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{session_id}", response_model=dict[str, str])
async def delete_session(
    session_id: str,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """Delete a conversation session.

    Args:
        session_id: Session UUID
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {"message": "Session deleted"}

    Raises:
        404: Session not found
        400: Invalid context parameters
    """
    # Validate context parameters
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(f"🗑️ 删除会话: {session_id[:16]}...")
    try:
        await session_service.delete_session(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        )
        logger.info("✅ 会话已删除")
        return {"message": "Session deleted"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/save", response_model=dict[str, str])
async def save_temporary_session(
    session_id: str,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """Convert a temporary session to a permanent one.

    Args:
        session_id: Session UUID
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {"message": "Session saved"}

    Raises:
        404: Session not found
        400: Invalid context parameters
    """
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(f"Saving temporary session: {session_id[:16]}...")
    try:
        await session_service.save_temporary_session(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        )
        logger.info("Session saved successfully")
        return {"message": "Session saved"}
    except FileNotFoundError:
        logger.error(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{session_id}/model", response_model=dict[str, str])
async def update_session_model(
    session_id: str,
    request: UpdateModelRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """更新会话使用的模型.

    Args:
        session_id: 会话 UUID
        request: 包含新模型 ID 的请求体
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {"message": "Model updated successfully"}

    Raises:
        404: Session not found
        400: Invalid context parameters
    """
    # Validate context parameters
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(f"🔄 更新会话模型: {session_id[:16]} -> {request.model_id}")
    try:
        await session_service.update_session_target(
            session_id=session_id,
            target_type="model",
            model_id=request.model_id,
            context_type=context_type,
            project_id=project_id,
        )
        logger.info("✅ 模型更新成功")
        return {"message": "Model updated successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{session_id}/assistant", response_model=dict[str, str])
async def update_session_assistant(
    session_id: str,
    request: UpdateAssistantRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """更新会话使用的助手.

    Args:
        session_id: 会话 UUID
        request: 包含新助手 ID 的请求体
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {"message": "Assistant updated successfully"}

    Raises:
        404: Session not found
        400: Assistant not found or invalid context parameters
    """
    # Validate context parameters
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(f"🔄 更新会话助手: {session_id[:16]} -> {request.assistant_id}")
    try:
        await session_service.update_session_target(
            session_id=session_id,
            target_type="assistant",
            assistant_id=request.assistant_id,
            context_type=context_type,
            project_id=project_id,
        )
        logger.info("✅ 助手更新成功")
        return {"message": "Assistant updated successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 助手错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{session_id}/target", response_model=dict[str, str])
async def update_session_target(
    session_id: str,
    request: UpdateTargetRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """Update session chat target (assistant or model)."""
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(
        "🔄 更新会话目标: %s -> %s (assistant=%s model=%s)",
        session_id[:16],
        request.target_type,
        request.assistant_id,
        request.model_id,
    )
    try:
        await session_service.update_session_target(
            session_id=session_id,
            target_type=request.target_type,
            assistant_id=request.assistant_id,
            model_id=request.model_id,
            context_type=context_type,
            project_id=project_id,
        )
        return {"message": "Session target updated successfully"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class UpdateGroupAssistantsRequest(BaseModel):
    """Update group assistants request"""

    group_assistants: list[str]


class UpdateGroupSettingsRequest(BaseModel):
    """Update group chat structured settings."""

    group_assistants: list[str] | None = None
    group_mode: str | None = None
    group_settings: dict[str, Any] | None = None


@router.put("/{session_id}/group-assistants", response_model=dict[str, str])
async def update_group_assistants(
    session_id: str,
    request: UpdateGroupAssistantsRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """Update the group assistants list for a session.

    Args:
        session_id: Session UUID
        request: Contains list of assistant IDs (min 2)
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {"message": "Group assistants updated"}

    Raises:
        404: Session not found
        400: Invalid assistant IDs or less than 2 provided
    """
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(
        f"Updating group assistants for session {session_id[:16]}: {request.group_assistants}"
    )
    try:
        await session_service.update_group_assistants(
            session_id=session_id,
            group_assistants=request.group_assistants,
            context_type=context_type,
            project_id=project_id,
        )
        return {"message": "Group assistants updated"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{session_id}/group-settings", response_model=dict[str, Any])
async def get_group_settings(
    session_id: str,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """Read structured group settings with effective runtime values."""
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    try:
        return await session_service.get_group_settings(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{session_id}/group-settings", response_model=dict[str, Any])
async def update_group_settings(
    session_id: str,
    request: UpdateGroupSettingsRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """Update group_mode/group_assistants/group_settings for one session."""
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    try:
        return await session_service.update_group_settings(
            session_id=session_id,
            group_assistants=request.group_assistants,
            group_mode=request.group_mode,
            group_settings=request.group_settings,
            context_type=context_type,
            project_id=project_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{session_id}/title", response_model=dict[str, str])
async def update_session_title(
    session_id: str,
    request: UpdateTitleRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """更新会话标题.

    Args:
        session_id: 会话 UUID
        request: 包含新标题的请求体
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {"message": "Title updated successfully"}

    Raises:
        404: Session not found
        400: Invalid context parameters
    """
    # Validate context parameters
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(f"✏️ 更新会话标题: {session_id[:16]} -> {request.title}")
    try:
        await session_service.update_session_title(
            session_id=session_id,
            title=request.title,
            context_type=context_type,
            project_id=project_id,
        )
        logger.info("✅ 标题更新成功")
        return {"message": "Title updated successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{session_id}/param-overrides", response_model=dict[str, str])
async def update_param_overrides(
    session_id: str,
    request: UpdateParamOverridesRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """Update per-session parameter overrides.

    Args:
        session_id: Session UUID
        request: Contains param_overrides dict with allowed keys
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {"message": "Parameter overrides updated"}
    """
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    overrides = request.param_overrides
    logger.info(f"Updating param overrides for session {session_id[:16]}: {overrides}")
    try:
        await session_service.update_param_overrides(
            session_id=session_id,
            overrides=overrides,
            context_type=context_type,
            project_id=project_id,
        )
        return {"message": "Parameter overrides updated"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class BranchSessionRequest(BaseModel):
    """Branch session request"""

    message_id: str


@router.post("/{session_id}/branch", response_model=dict[str, str])
async def branch_session(
    session_id: str,
    request: BranchSessionRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """Branch a session from a specific message.

    Creates a new session containing only messages up to and including the
    specified message_id.

    Args:
        session_id: Source session UUID
        request: Contains message_id to branch from
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {"session_id": "new-uuid", "message": "Session branched successfully"}

    Raises:
        404: Session not found
        400: message_id not found or invalid context parameters
    """
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(f"Branching session: {session_id[:16]} from message {request.message_id}...")
    try:
        new_session_id = await session_service.branch_session(
            session_id=session_id,
            message_id=request.message_id,
            context_type=context_type,
            project_id=project_id,
        )
        logger.info(f"Session branched successfully: {new_session_id}")
        return {"session_id": new_session_id, "message": "Session branched successfully"}
    except FileNotFoundError:
        logger.error(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/duplicate", response_model=dict[str, str])
async def duplicate_session(
    session_id: str,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """复制会话.

    Args:
        session_id: 要复制的会话 UUID
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        {"session_id": "new-uuid", "message": "Session duplicated successfully"}

    Raises:
        404: Session not found
        400: Invalid context parameters
    """
    # Validate context parameters
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(f"📋 复制会话: {session_id[:16]}...")
    try:
        new_session_id = await session_service.duplicate_session(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        )
        logger.info(f"✅ 会话复制成功: {new_session_id}")
        return {"session_id": new_session_id, "message": "Session duplicated successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/move", response_model=dict[str, str])
async def move_session(
    session_id: str,
    request: TransferSessionRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """Move a session between chat/projects context."""
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    if request.target_context_type == "project" and not request.target_project_id:
        raise HTTPException(
            status_code=400, detail="target_project_id is required for project context"
        )

    if request.target_context_type not in ["chat", "project"]:
        raise HTTPException(status_code=400, detail="Invalid target_context_type")

    logger.info(
        f"📦 移动会话: {session_id[:16]} -> {request.target_context_type}:{request.target_project_id or '-'}"
    )
    try:
        await session_service.move_session(
            session_id=session_id,
            source_context_type=context_type,
            source_project_id=project_id,
            target_context_type=request.target_context_type,
            target_project_id=request.target_project_id,
        )
        return {"session_id": session_id, "message": "Session moved successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except FileExistsError as e:
        logger.error(f"❌ 目标已存在: {str(e)}")
        raise HTTPException(status_code=409, detail="Target session already exists")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/copy", response_model=dict[str, str])
async def copy_session(
    session_id: str,
    request: TransferSessionRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """Copy a session between chat/projects context."""
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    if request.target_context_type == "project" and not request.target_project_id:
        raise HTTPException(
            status_code=400, detail="target_project_id is required for project context"
        )

    if request.target_context_type not in ["chat", "project"]:
        raise HTTPException(status_code=400, detail="Invalid target_context_type")

    logger.info(
        f"📄 复制会话: {session_id[:16]} -> {request.target_context_type}:{request.target_project_id or '-'}"
    )
    try:
        new_session_id = await session_service.copy_session(
            session_id=session_id,
            source_context_type=context_type,
            source_project_id=project_id,
            target_context_type=request.target_context_type,
            target_project_id=request.target_project_id,
        )
        return {"session_id": new_session_id, "message": "Session copied successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


def _format_thinking_block(content: str) -> str:
    """Extract thinking blocks from content and format as collapsible details."""
    think_pattern = re.compile(r"<think>(.*?)</think>", re.DOTALL)
    match = think_pattern.search(content)
    if not match:
        return content

    thinking_text = match.group(1).strip()
    # Remove the <think>...</think> from main content
    main_content = think_pattern.sub("", content).strip()

    # Build collapsible thinking block
    thinking_html = f"<details>\n<summary>Thinking</summary>\n\n{thinking_text}\n\n</details>\n"

    return f"{thinking_html}\n{main_content}"


def _build_export_markdown(session: dict) -> str:
    """Build clean export markdown from a session."""
    title = session.get("title", "Untitled")
    messages = session.get("state", {}).get("messages", [])

    lines = [f"# {title}\n"]

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            lines.append("---")
            lines.append("## User\n")
            lines.append(content)
            lines.append("")
        elif role == "assistant":
            lines.append("---")
            lines.append("## Assistant\n")
            formatted = _format_thinking_block(content)
            lines.append(formatted)
            lines.append("")
        # Skip separator and summary messages

    return "\n".join(lines)


@router.get("/{session_id}/export")
async def export_session(
    session_id: str,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    storage: ConversationQueryStorageLike = Depends(get_storage),
):
    """Export a conversation session as a clean Markdown file.

    Returns a downloadable .md file with user/assistant messages,
    stripped of internal metadata (usage, cost, message IDs).

    Args:
        session_id: Session UUID
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Raises:
        404: Session not found
        400: Invalid context parameters
    """
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(f"Exporting session: {session_id[:16]}...")
    try:
        session = await storage.get_session(
            session_id, context_type=context_type, project_id=project_id
        )
        markdown_content = _build_export_markdown(session)

        # Build filename from title
        title = session.get("title", "conversation")
        # Sanitize title for filename
        safe_title = re.sub(r'[\\/*?:"<>|]', "_", title).strip()
        if not safe_title:
            safe_title = "conversation"
        filename = f"{safe_title}.md"
        encoded_filename = quote(filename)

        return Response(
            content=markdown_content.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
        )
    except FileNotFoundError:
        logger.error(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import/chatgpt", response_model=ImportChatGPTResponse)
async def import_chatgpt_conversations(
    file: UploadFile = File(...),
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    storage: ConversationImportStorageLike = Depends(get_storage),
):
    """Import ChatGPT conversations from exported conversations.json."""
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    raw = await file.read()
    filename = (file.filename or "").lower()

    text: str
    if filename.endswith(".zip") or zipfile.is_zipfile(io.BytesIO(raw)):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zip_file:
                json_name = None
                for name in zip_file.namelist():
                    if name.lower().endswith("conversations.json"):
                        json_name = name
                        break
                if not json_name:
                    raise HTTPException(
                        status_code=400, detail="ZIP does not contain conversations.json"
                    )
                json_bytes = zip_file.read(json_name)
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Invalid ZIP file") from exc

        try:
            text = json_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = json_bytes.decode("utf-8-sig", errors="replace")
    else:
        if filename and not filename.endswith(".json"):
            raise HTTPException(
                status_code=400, detail="Please upload a ChatGPT .json or .zip export file"
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8-sig", errors="replace")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {exc}") from exc

    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="Expected a list of conversations in JSON")

    importer = ChatGPTImportService(storage)
    result = await importer.import_conversations(
        payload, context_type=context_type, project_id=project_id
    )
    return result


@router.post("/import/markdown", response_model=ImportChatGPTResponse)
async def import_markdown_conversation(
    file: UploadFile = File(...),
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    storage: ConversationImportStorageLike = Depends(get_storage),
):
    """Import a Markdown conversation file."""
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    filename = (file.filename or "").lower()
    if filename and not (filename.endswith(".md") or filename.endswith(".markdown")):
        raise HTTPException(status_code=400, detail="Please upload a Markdown (.md) file")

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8-sig", errors="replace")

    importer = MarkdownImportService(storage)
    result = await importer.import_markdown(
        text, filename=file.filename, context_type=context_type, project_id=project_id
    )
    return result


@router.put("/{session_id}/folder", status_code=204)
async def update_session_folder(
    session_id: str,
    request: dict = Body(...),
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    session_service: SessionApplicationServiceLike = Depends(get_session_application_service),
):
    """
    Update session's folder assignment.

    Args:
        session_id: Session UUID
        request: { folder_id: str | null }
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Raises:
        404: Session not found
        400: Invalid context parameters
    """
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    try:
        folder_id = request.get("folder_id")
        await session_service.update_session_folder(
            session_id=session_id,
            folder_id=folder_id,
            context_type=context_type,
            project_id=project_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
