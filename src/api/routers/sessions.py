"""Session management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, List, Optional
from pydantic import BaseModel
import logging

from ..services.conversation_storage import ConversationStorage
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    model_id: Optional[str] = None  # 向后兼容
    assistant_id: Optional[str] = None  # 新方式：使用助手


class UpdateModelRequest(BaseModel):
    """更新模型请求"""
    model_id: str


class UpdateAssistantRequest(BaseModel):
    """更新助手请求"""
    assistant_id: str


class UpdateTitleRequest(BaseModel):
    """更新标题请求"""
    title: str


def get_storage() -> ConversationStorage:
    """Dependency injection for ConversationStorage."""
    return ConversationStorage(settings.conversations_dir)


@router.post("", response_model=Dict[str, str])
async def create_session(
    request: Optional[CreateSessionRequest] = None,
    storage: ConversationStorage = Depends(get_storage)
):
    """Create a new conversation session.

    Args:
        request: 可选的创建会话请求（包含 assistant_id 或 model_id）

    Returns:
        {"session_id": "uuid-string"}
    """
    assistant_id = request.assistant_id if request else None
    model_id = request.model_id if request else None
    logger.info(f"📝 创建新会话（助手: {assistant_id or '默认'}, 模型: {model_id or '默认'}）...")
    session_id = await storage.create_session(model_id=model_id, assistant_id=assistant_id)
    logger.info(f"✅ 新会话已创建: {session_id}")
    return {"session_id": session_id}


@router.get("", response_model=Dict[str, List[Dict]])
async def list_sessions(storage: ConversationStorage = Depends(get_storage)):
    """List all conversation sessions.

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
    """
    logger.info("📋 列出所有会话...")
    sessions = await storage.list_sessions()
    logger.info(f"✅ 找到 {len(sessions)} 个会话")
    return {"sessions": sessions}


@router.get("/{session_id}", response_model=Dict)
async def get_session(
    session_id: str,
    storage: ConversationStorage = Depends(get_storage)
):
    """Get a specific conversation session with full history.

    Args:
        session_id: Session UUID

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
    """
    logger.info(f"📂 获取会话: {session_id[:16]}...")
    try:
        session = await storage.get_session(session_id)
        msg_count = len(session.get('state', {}).get('messages', []))
        logger.info(f"✅ 会话加载成功，包含 {msg_count} 条消息")
        return session
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/{session_id}", response_model=Dict[str, str])
async def delete_session(
    session_id: str,
    storage: ConversationStorage = Depends(get_storage)
):
    """Delete a conversation session.

    Args:
        session_id: Session UUID

    Returns:
        {"message": "Session deleted"}

    Raises:
        404: Session not found
    """
    logger.info(f"🗑️ 删除会话: {session_id[:16]}...")
    try:
        await storage.delete_session(session_id)
        logger.info(f"✅ 会话已删除")
        return {"message": "Session deleted"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")


@router.put("/{session_id}/model", response_model=Dict[str, str])
async def update_session_model(
    session_id: str,
    request: UpdateModelRequest,
    storage: ConversationStorage = Depends(get_storage)
):
    """更新会话使用的模型.

    Args:
        session_id: 会话 UUID
        request: 包含新模型 ID 的请求体

    Returns:
        {"message": "Model updated successfully"}

    Raises:
        404: Session not found
    """
    logger.info(f"🔄 更新会话模型: {session_id[:16]} -> {request.model_id}")
    try:
        await storage.update_session_model(session_id, request.model_id)
        logger.info(f"✅ 模型更新成功")
        return {"message": "Model updated successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")


@router.put("/{session_id}/assistant", response_model=Dict[str, str])
async def update_session_assistant(
    session_id: str,
    request: UpdateAssistantRequest,
    storage: ConversationStorage = Depends(get_storage)
):
    """更新会话使用的助手.

    Args:
        session_id: 会话 UUID
        request: 包含新助手 ID 的请求体

    Returns:
        {"message": "Assistant updated successfully"}

    Raises:
        404: Session not found
        400: Assistant not found
    """
    logger.info(f"🔄 更新会话助手: {session_id[:16]} -> {request.assistant_id}")
    try:
        await storage.update_session_assistant(session_id, request.assistant_id)
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
    storage: ConversationStorage = Depends(get_storage)
):
    """更新会话标题.

    Args:
        session_id: 会话 UUID
        request: 包含新标题的请求体

    Returns:
        {"message": "Title updated successfully"}

    Raises:
        404: Session not found
    """
    logger.info(f"✏️ 更新会话标题: {session_id[:16]} -> {request.title}")
    try:
        await storage.update_session_metadata(session_id, {"title": request.title})
        logger.info(f"✅ 标题更新成功")
        return {"message": "Title updated successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/{session_id}/duplicate", response_model=Dict[str, str])
async def duplicate_session(
    session_id: str,
    storage: ConversationStorage = Depends(get_storage)
):
    """复制会话.

    Args:
        session_id: 要复制的会话 UUID

    Returns:
        {"session_id": "new-uuid", "message": "Session duplicated successfully"}

    Raises:
        404: Session not found
    """
    logger.info(f"📋 复制会话: {session_id[:16]}...")
    try:
        # Get the original session
        original_session = await storage.get_session(session_id)

        # Create a new session with the same model/assistant
        assistant_id = original_session.get('assistant_id')
        model_id = original_session.get('model_id')
        new_session_id = await storage.create_session(model_id=model_id, assistant_id=assistant_id)

        # Copy the title with a suffix
        original_title = original_session.get('title', 'New Chat')
        new_title = f"{original_title} (Copy)"
        await storage.update_session_metadata(new_session_id, {"title": new_title})

        # Copy the messages using set_messages method
        original_messages = original_session.get('state', {}).get('messages', [])
        if original_messages:
            await storage.set_messages(new_session_id, original_messages)

        logger.info(f"✅ 会话复制成功: {new_session_id}")
        return {"session_id": new_session_id, "message": "Session duplicated successfully"}
    except FileNotFoundError:
        logger.error(f"❌ 会话未找到: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
