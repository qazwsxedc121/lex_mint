"""Chat API endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import logging
import json

# 使用简化版 AgentService（不使用 LangGraph）
from ..services.agent_service_simple import AgentService
from ..services.conversation_storage import ConversationStorage
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    session_id: str
    message: str
    truncate_after_index: Optional[int] = None  # 截断索引，删除此索引之后的消息
    skip_user_message: bool = False  # 是否跳过追加用户消息（重新生成时使用）


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    session_id: str
    response: str


def get_agent_service() -> AgentService:
    """Dependency injection for AgentService."""
    storage = ConversationStorage(settings.conversations_dir)
    return AgentService(storage)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent: AgentService = Depends(get_agent_service)
):
    """Send a message and receive AI response.

    Args:
        request: ChatRequest with session_id and message

    Returns:
        ChatResponse with session_id and AI response

    Raises:
        404: Session not found
        500: Internal server error (agent failure)
    """
    # 使用 print 强制输出，绕过日志系统
    print("=" * 80)
    print(f"📨 收到聊天请求")
    print(f"   Session ID: {request.session_id[:16]}...")
    print(f"   用户消息: {request.message[:100]}{'...' if len(request.message) > 100 else ''}")
    print("=" * 80)

    logger.info("=" * 80)
    logger.info(f"📨 收到聊天请求")
    logger.info(f"   Session ID: {request.session_id[:16]}...")
    logger.info(f"   用户消息: {request.message[:100]}{'...' if len(request.message) > 100 else ''}")
    logger.info("=" * 80)

    try:
        print("🤖 开始处理消息...")
        logger.info("🤖 开始处理消息...")

        response = await agent.process_message(request.session_id, request.message)

        print("=" * 80)
        print("✅ 消息处理完成")
        print(f"   AI 回复: {response[:100]}{'...' if len(response) > 100 else ''}")
        print("=" * 80)

        logger.info("=" * 80)
        logger.info("✅ 消息处理完成")
        logger.info(f"   AI 回复: {response[:100]}{'...' if len(response) > 100 else ''}")
        logger.info("=" * 80)

        return ChatResponse(session_id=request.session_id, response=response)
    except FileNotFoundError as e:
        print(f"❌ 会话未找到: {request.session_id}")
        logger.error(f"❌ 会话未找到: {request.session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        print(f"❌ Agent 错误: {str(e)}")
        logger.error(f"❌ Agent 错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    agent: AgentService = Depends(get_agent_service)
):
    """流式发送消息并接收 AI 响应.

    Args:
        request: ChatRequest with session_id and message

    Returns:
        StreamingResponse with Server-Sent Events

    Raises:
        404: Session not found
        500: Internal server error (agent failure)
    """
    print("=" * 80)
    print(f"📨 收到流式聊天请求")
    print(f"   Session ID: {request.session_id[:16]}...")
    print(f"   用户消息: {request.message[:100]}{'...' if len(request.message) > 100 else ''}")
    print("=" * 80)

    logger.info("=" * 80)
    logger.info(f"📨 收到流式聊天请求")
    logger.info(f"   Session ID: {request.session_id[:16]}...")
    logger.info(f"   用户消息: {request.message[:100]}{'...' if len(request.message) > 100 else ''}")
    logger.info("=" * 80)

    async def event_generator():
        """生成 SSE (Server-Sent Events) 格式的数据流"""
        try:
            print("🤖 开始流式处理消息...")
            logger.info("🤖 开始流式处理消息...")

            # 如果指定了截断索引，先截断消息
            if request.truncate_after_index is not None:
                print(f"✂️ 截断消息到索引 {request.truncate_after_index}")
                logger.info(f"✂️ 截断消息到索引 {request.truncate_after_index}")
                await agent.storage.truncate_messages_after(
                    request.session_id,
                    request.truncate_after_index
                )

            # 流式处理消息
            async for chunk in agent.process_message_stream(
                request.session_id,
                request.message,
                skip_user_append=request.skip_user_message
            ):
                # SSE 格式: data: {json}\n\n
                data = json.dumps({"chunk": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"

            # 发送结束标记
            yield f"data: {json.dumps({'done': True})}\n\n"

            print("=" * 80)
            print("✅ 流式消息处理完成")
            print("=" * 80)

            logger.info("=" * 80)
            logger.info("✅ 流式消息处理完成")
            logger.info("=" * 80)

        except FileNotFoundError as e:
            print(f"❌ 会话未找到: {request.session_id}")
            logger.error(f"❌ 会话未找到: {request.session_id}")
            error_data = json.dumps({"error": "Session not found"})
            yield f"data: {error_data}\n\n"
        except Exception as e:
            print(f"❌ Agent 错误: {str(e)}")
            logger.error(f"❌ Agent 错误: {str(e)}", exc_info=True)
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        }
    )
