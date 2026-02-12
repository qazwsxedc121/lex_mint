"""Session management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Body, Query, UploadFile, File
from fastapi.responses import Response
from typing import Dict, List, Optional
from pydantic import BaseModel
import logging
import re
import json
import io
import zipfile
import shutil
from urllib.parse import quote

from ..services.conversation_storage import ConversationStorage
from ..services.comparison_storage import ComparisonStorage
from ..services.chatgpt_import_service import ChatGPTImportService
from ..services.markdown_import_service import MarkdownImportService
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    model_id: Optional[str] = None  # 向后兼容
    assistant_id: Optional[str] = None  # 新方式：使用助手
    temporary: bool = False


class UpdateModelRequest(BaseModel):
    """更新模型请求"""
    model_id: str


class UpdateAssistantRequest(BaseModel):
    """更新助手请求"""
    assistant_id: str


class UpdateTitleRequest(BaseModel):
    """更新标题请求"""
    title: str


class UpdateParamOverridesRequest(BaseModel):
    """更新参数覆盖请求"""
    param_overrides: Dict


class TransferSessionRequest(BaseModel):
    """Move or copy session request."""
    target_context_type: str
    target_project_id: Optional[str] = None


class ImportChatGPTSession(BaseModel):
    """Imported session summary."""
    session_id: str
    title: str
    message_count: int


class ImportChatGPTResponse(BaseModel):
    """ChatGPT import response."""
    imported: int
    skipped: int
    sessions: List[ImportChatGPTSession]
    errors: List[str]


def get_storage() -> ConversationStorage:
    """Dependency injection for ConversationStorage."""
    return ConversationStorage(settings.conversations_dir)


@router.post("", response_model=Dict[str, str])
async def create_session(
    request: Optional[CreateSessionRequest] = None,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
    temporary = request.temporary if request else False
    logger.info(f"📝 创建新会话（助手: {assistant_id or '默认'}, 模型: {model_id or '默认'}, 临时: {temporary}）...")

    try:
        session_id = await storage.create_session(
            model_id=model_id,
            assistant_id=assistant_id,
            context_type=context_type,
            project_id=project_id,
            temporary=temporary
        )
        logger.info(f"✅ 新会话已创建: {session_id}")
        return {"session_id": session_id}
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=Dict[str, List[Dict]])
async def list_sessions(
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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


@router.get("/search", response_model=Dict[str, List[Dict]])
async def search_sessions(
    q: str = Query(""),
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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


@router.get("/{session_id}", response_model=Dict)
async def get_session(
    session_id: str,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
        session = await storage.get_session(session_id, context_type=context_type, project_id=project_id)

        # Load comparison data if it exists
        try:
            comparison_storage = ComparisonStorage(settings.conversations_dir)
            compare_data = await comparison_storage.load(session_id, context_type=context_type, project_id=project_id)
            if compare_data:
                session["compare_data"] = compare_data
        except Exception as e:
            logger.warning(f"Failed to load comparison data: {e}")

        msg_count = len(session.get('state', {}).get('messages', []))
        logger.info(f"✅ 会话加载成功，包含 {msg_count} 条消息")
        return session
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{session_id}", response_model=Dict[str, str])
async def delete_session(
    session_id: str,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
        await storage.delete_session(session_id, context_type=context_type, project_id=project_id)
        logger.info(f"✅ 会话已删除")
        return {"message": "Session deleted"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/save", response_model=Dict[str, str])
async def save_temporary_session(
    session_id: str,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
        await storage.convert_to_permanent(session_id, context_type=context_type, project_id=project_id)
        logger.info(f"Session saved successfully")
        return {"message": "Session saved"}
    except FileNotFoundError:
        logger.error(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{session_id}/model", response_model=Dict[str, str])
async def update_session_model(
    session_id: str,
    request: UpdateModelRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
        await storage.update_session_model(session_id, request.model_id, context_type=context_type, project_id=project_id)
        logger.info(f"✅ 模型更新成功")
        return {"message": "Model updated successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{session_id}/assistant", response_model=Dict[str, str])
async def update_session_assistant(
    session_id: str,
    request: UpdateAssistantRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
        await storage.update_session_assistant(session_id, request.assistant_id, context_type=context_type, project_id=project_id)
        logger.info(f"✅ 助手更新成功")
        return {"message": "Assistant updated successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 助手错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{session_id}/title", response_model=Dict[str, str])
async def update_session_title(
    session_id: str,
    request: UpdateTitleRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
        await storage.update_session_metadata(session_id, {"title": request.title}, context_type=context_type, project_id=project_id)
        logger.info(f"✅ 标题更新成功")
        return {"message": "Title updated successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


ALLOWED_OVERRIDE_KEYS = {
    "model_id", "temperature", "max_tokens", "top_p", "top_k",
    "frequency_penalty", "presence_penalty", "max_rounds"
}

PARAM_RANGES = {
    "temperature": (0, 2),
    "max_tokens": (1, 8192),
    "top_p": (0, 1),
    "top_k": (1, 200),
    "frequency_penalty": (-2, 2),
    "presence_penalty": (-2, 2),
    "max_rounds": (-1, 1000),
}


@router.put("/{session_id}/param-overrides", response_model=Dict[str, str])
async def update_param_overrides(
    session_id: str,
    request: UpdateParamOverridesRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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

    # Validate keys
    invalid_keys = set(overrides.keys()) - ALLOWED_OVERRIDE_KEYS
    if invalid_keys:
        raise HTTPException(status_code=400, detail=f"Invalid override keys: {invalid_keys}")

    # Validate ranges for numeric parameters
    for key, value in overrides.items():
        if key == "model_id":
            if not isinstance(value, str) or ':' not in value:
                raise HTTPException(status_code=400, detail="model_id must be in 'provider:model' format")
            # Validate model exists
            from ..services.model_config_service import ModelConfigService
            model_service = ModelConfigService()
            parts = value.split(":", 1)
            model = await model_service.get_model(parts[1])
            if not model:
                raise HTTPException(status_code=400, detail=f"Model '{value}' not found")
            continue

        if key in PARAM_RANGES:
            if not isinstance(value, (int, float)):
                raise HTTPException(status_code=400, detail=f"{key} must be a number")
            min_val, max_val = PARAM_RANGES[key]
            if value < min_val or value > max_val:
                raise HTTPException(status_code=400, detail=f"{key} must be between {min_val} and {max_val}")

    logger.info(f"Updating param overrides for session {session_id[:16]}: {overrides}")
    try:
        await storage.update_session_metadata(
            session_id, {"param_overrides": overrides},
            context_type=context_type, project_id=project_id
        )
        return {"message": "Parameter overrides updated"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class BranchSessionRequest(BaseModel):
    """Branch session request"""
    message_id: str


@router.post("/{session_id}/branch", response_model=Dict[str, str])
async def branch_session(
    session_id: str,
    request: BranchSessionRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
        original_session = await storage.get_session(session_id, context_type=context_type, project_id=project_id)

        # Find the message by message_id
        original_messages = original_session.get('state', {}).get('messages', [])
        branch_index = None
        for i, msg in enumerate(original_messages):
            if msg.get('message_id') == request.message_id:
                branch_index = i
                break

        if branch_index is None:
            raise HTTPException(status_code=400, detail=f"message_id '{request.message_id}' not found in session")

        truncated_messages = original_messages[:branch_index + 1]

        # Create new session with same model/assistant
        assistant_id = original_session.get('assistant_id')
        model_id = original_session.get('model_id')
        new_session_id = await storage.create_session(
            model_id=model_id,
            assistant_id=assistant_id,
            context_type=context_type,
            project_id=project_id
        )

        # Set title with Branch suffix
        original_title = original_session.get('title', 'New Chat')
        new_title = f"{original_title} (Branch)"
        await storage.update_session_metadata(new_session_id, {"title": new_title}, context_type=context_type, project_id=project_id)

        # Copy truncated messages
        if truncated_messages:
            await storage.set_messages(new_session_id, truncated_messages, context_type=context_type, project_id=project_id)

        logger.info(f"Session branched successfully: {new_session_id} with {len(truncated_messages)} messages")
        return {"session_id": new_session_id, "message": "Session branched successfully"}
    except FileNotFoundError:
        logger.error(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/duplicate", response_model=Dict[str, str])
async def duplicate_session(
    session_id: str,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
        # Get the original session
        original_session = await storage.get_session(session_id, context_type=context_type, project_id=project_id)

        # Create a new session with the same model/assistant in the same context
        assistant_id = original_session.get('assistant_id')
        model_id = original_session.get('model_id')
        new_session_id = await storage.create_session(
            model_id=model_id,
            assistant_id=assistant_id,
            context_type=context_type,
            project_id=project_id
        )

        # Copy the title with a suffix
        original_title = original_session.get('title', 'New Chat')
        new_title = f"{original_title} (Copy)"
        await storage.update_session_metadata(new_session_id, {"title": new_title}, context_type=context_type, project_id=project_id)

        # Copy the messages using set_messages method
        original_messages = original_session.get('state', {}).get('messages', [])
        if original_messages:
            await storage.set_messages(new_session_id, original_messages, context_type=context_type, project_id=project_id)

        logger.info(f"✅ 会话复制成功: {new_session_id}")
        return {"session_id": new_session_id, "message": "Session duplicated successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


def _copy_session_attachments(source_session_id: str, target_session_id: str) -> None:
    """Copy attachment files for a session to a new session ID."""
    source_dir = settings.attachments_dir / source_session_id
    if not source_dir.exists():
        return

    target_dir = settings.attachments_dir / target_session_id
    target_dir.mkdir(parents=True, exist_ok=True)

    for entry in source_dir.iterdir():
        if entry.name == "temp":
            continue
        destination = target_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, destination)


@router.post("/{session_id}/move", response_model=Dict[str, str])
async def move_session(
    session_id: str,
    request: TransferSessionRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
):
    """Move a session between chat/projects context."""
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    if request.target_context_type == "project" and not request.target_project_id:
        raise HTTPException(status_code=400, detail="target_project_id is required for project context")

    if request.target_context_type not in ["chat", "project"]:
        raise HTTPException(status_code=400, detail="Invalid target_context_type")

    logger.info(f"📦 移动会话: {session_id[:16]} -> {request.target_context_type}:{request.target_project_id or '-'}")
    try:
        await storage.move_session(
            session_id,
            source_context_type=context_type,
            source_project_id=project_id,
            target_context_type=request.target_context_type,
            target_project_id=request.target_project_id
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


@router.post("/{session_id}/copy", response_model=Dict[str, str])
async def copy_session(
    session_id: str,
    request: TransferSessionRequest,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
):
    """Copy a session between chat/projects context."""
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    if request.target_context_type == "project" and not request.target_project_id:
        raise HTTPException(status_code=400, detail="target_project_id is required for project context")

    if request.target_context_type not in ["chat", "project"]:
        raise HTTPException(status_code=400, detail="Invalid target_context_type")

    logger.info(f"📄 复制会话: {session_id[:16]} -> {request.target_context_type}:{request.target_project_id or '-'}")
    try:
        new_session_id = await storage.copy_session(
            session_id,
            source_context_type=context_type,
            source_project_id=project_id,
            target_context_type=request.target_context_type,
            target_project_id=request.target_project_id
        )

        try:
            _copy_session_attachments(session_id, new_session_id)
        except Exception as e:
            logger.warning(f"⚠️ 附件复制失败: {session_id} -> {new_session_id}: {e}")

        return {"session_id": new_session_id, "message": "Session copied successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


def _format_thinking_block(content: str) -> str:
    """Extract thinking blocks from content and format as collapsible details."""
    think_pattern = re.compile(r'<think>(.*?)</think>', re.DOTALL)
    match = think_pattern.search(content)
    if not match:
        return content

    thinking_text = match.group(1).strip()
    # Remove the <think>...</think> from main content
    main_content = think_pattern.sub('', content).strip()

    # Build collapsible thinking block
    thinking_html = (
        '<details>\n'
        '<summary>Thinking</summary>\n\n'
        f'{thinking_text}\n\n'
        '</details>\n'
    )

    return f'{thinking_html}\n{main_content}'


def _build_export_markdown(session: dict) -> str:
    """Build clean export markdown from a session."""
    title = session.get('title', 'Untitled')
    messages = session.get('state', {}).get('messages', [])

    lines = [f'# {title}\n']

    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '')

        if role == 'user':
            lines.append('---')
            lines.append('## User\n')
            lines.append(content)
            lines.append('')
        elif role == 'assistant':
            lines.append('---')
            lines.append('## Assistant\n')
            formatted = _format_thinking_block(content)
            lines.append(formatted)
            lines.append('')
        # Skip separator and summary messages

    return '\n'.join(lines)


@router.get("/{session_id}/export")
async def export_session(
    session_id: str,
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
        session = await storage.get_session(session_id, context_type=context_type, project_id=project_id)
        markdown_content = _build_export_markdown(session)

        # Build filename from title
        title = session.get('title', 'conversation')
        # Sanitize title for filename
        safe_title = re.sub(r'[\\/*?:"<>|]', '_', title).strip()
        if not safe_title:
            safe_title = 'conversation'
        filename = f'{safe_title}.md'
        encoded_filename = quote(filename)

        return Response(
            content=markdown_content.encode('utf-8'),
            media_type='text/markdown; charset=utf-8',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
            }
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
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
                    raise HTTPException(status_code=400, detail="ZIP does not contain conversations.json")
                json_bytes = zip_file.read(json_name)
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Invalid ZIP file") from exc

        try:
            text = json_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = json_bytes.decode("utf-8-sig", errors="replace")
    else:
        if filename and not filename.endswith(".json"):
            raise HTTPException(status_code=400, detail="Please upload a ChatGPT .json or .zip export file")
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
        payload,
        context_type=context_type,
        project_id=project_id
    )
    return result


@router.post("/import/markdown", response_model=ImportChatGPTResponse)
async def import_markdown_conversation(
    file: UploadFile = File(...),
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
        text,
        filename=file.filename,
        context_type=context_type,
        project_id=project_id
    )
    return result


@router.put("/{session_id}/folder", status_code=204)
async def update_session_folder(
    session_id: str,
    request: Dict = Body(...),
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    storage: ConversationStorage = Depends(get_storage)
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
        await storage.update_session_folder(
            session_id=session_id,
            folder_id=folder_id,
            context_type=context_type,
            project_id=project_id
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
