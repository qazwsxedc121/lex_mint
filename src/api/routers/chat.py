"""Chat API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import json

# 使用简化版 AgentService（不使用 LangGraph）
from ..services.agent_service_simple import AgentService
from ..services.conversation_storage import ConversationStorage
from ..services.file_service import FileService
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


class FileAttachment(BaseModel):
    """File attachment metadata."""
    filename: str
    size: int
    mime_type: str


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    session_id: str
    message: str
    attachments: Optional[List[Dict[str, Any]]] = None  # List of {filename, size, mime_type, temp_path}
    truncate_after_index: Optional[int] = None  # 截断索引，删除此索引之后的消息
    skip_user_message: bool = False  # 是否跳过追加用户消息（重新生成时使用）
    reasoning_effort: Optional[str] = None  # Reasoning effort: "low", "medium", "high"


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    session_id: str
    response: str


class DeleteMessageRequest(BaseModel):
    """Request model for delete message endpoint."""
    session_id: str
    message_index: int


def get_agent_service() -> AgentService:
    """Dependency injection for AgentService."""
    storage = ConversationStorage(settings.conversations_dir)
    return AgentService(storage)


def get_file_service() -> FileService:
    """Dependency injection for FileService."""
    return FileService(settings.attachments_dir, settings.max_file_size_mb)


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
        """Generate SSE (Server-Sent Events) formatted data stream"""
        try:
            print("[SSE] Starting stream processing...")
            logger.info("[SSE] Starting stream processing...")

            # Truncate messages if specified
            if request.truncate_after_index is not None:
                print(f"[SSE] Truncating messages to index {request.truncate_after_index}")
                logger.info(f"[SSE] Truncating messages to index {request.truncate_after_index}")
                await agent.storage.truncate_messages_after(
                    request.session_id,
                    request.truncate_after_index
                )

            # Stream process messages
            async for chunk in agent.process_message_stream(
                request.session_id,
                request.message,
                skip_user_append=request.skip_user_message,
                reasoning_effort=request.reasoning_effort,
                attachments=request.attachments
            ):
                # Check if chunk is a usage/cost event (dict)
                if isinstance(chunk, dict) and chunk.get("type") == "usage":
                    # Send usage event separately
                    data = json.dumps(chunk, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                    continue

                # Regular content chunk (string)
                data = json.dumps({"chunk": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"

            # Send completion marker
            yield f"data: {json.dumps({'done': True})}\n\n"

            print("=" * 80)
            print("[OK] Stream processing complete")
            print("=" * 80)

            logger.info("=" * 80)
            logger.info("[OK] Stream processing complete")
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


@router.post("/chat/upload")
async def upload_file(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service)
):
    """Upload a text file attachment.

    Args:
        session_id: Session identifier
        file: Uploaded file

    Returns:
        File metadata including temp_path for later message send

    Raises:
        400: File validation failed (too large, wrong type)
        500: Upload failed
    """
    logger.info(f"File upload request: session={session_id[:16]}..., file={file.filename}")

    try:
        # Validate file
        await file_service.validate_file(file)

        # Save to temp location
        metadata = await file_service.save_temp_file(session_id, file)

        logger.info(f"File uploaded successfully: {metadata['filename']}")
        return metadata

    except ValueError as e:
        logger.error(f"File validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"File upload error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/chat/attachment/{session_id}/{message_index}/{filename}")
async def download_attachment(
    session_id: str,
    message_index: int,
    filename: str,
    file_service: FileService = Depends(get_file_service)
):
    """Download a file attachment.

    Args:
        session_id: Session identifier
        message_index: Message index
        filename: Filename

    Returns:
        File response

    Raises:
        404: File not found
        403: Access denied (path traversal attempt)
    """
    logger.info(f"File download request: session={session_id[:16]}..., index={message_index}, file={filename}")

    # Get file path
    filepath = file_service.get_file_path(session_id, message_index, filename)

    if not filepath:
        raise HTTPException(status_code=404, detail="File not found")

    # Security: ensure path is within attachments directory
    try:
        filepath.resolve().relative_to(file_service.attachments_dir.resolve())
    except ValueError:
        logger.error(f"Path traversal attempt detected: {filepath}")
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(
        filepath,
        media_type="application/octet-stream",
        filename=filename
    )


@router.delete("/chat/message")
async def delete_message(
    request: DeleteMessageRequest,
    agent: AgentService = Depends(get_agent_service)
):
    """Delete a single message from conversation.

    Args:
        request: DeleteMessageRequest with session_id and message_index

    Returns:
        Success message

    Raises:
        404: Session not found
        400: Invalid message index
        500: Internal server error
    """
    logger.info(f"Delete message request: session={request.session_id[:16]}..., index={request.message_index}")

    try:
        await agent.storage.delete_message(request.session_id, request.message_index)
        return {"success": True, "message": "Message deleted"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except IndexError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Delete message error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")
