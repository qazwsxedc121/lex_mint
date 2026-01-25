"""Session management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List
import logging

from ..services.conversation_storage import ConversationStorage
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def get_storage() -> ConversationStorage:
    """Dependency injection for ConversationStorage."""
    return ConversationStorage(settings.conversations_dir)


@router.post("", response_model=Dict[str, str])
async def create_session(storage: ConversationStorage = Depends(get_storage)):
    """Create a new conversation session.

    Returns:
        {"session_id": "uuid-string"}
    """
    logger.info("📝 创建新会话...")
    session_id = await storage.create_session()
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
