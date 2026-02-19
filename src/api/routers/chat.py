"""Chat API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, Query
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import json

# 使用简化版 AgentService（不使用 LangGraph）
from ..services.agent_service_simple import AgentService
from ..services.conversation_storage import ConversationStorage, create_storage_with_project_resolver
from ..services.file_service import FileService
from ..models.search import SearchSource
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
    file_references: Optional[List[Dict[str, str]]] = None  # List of {path, project_id} for @file references
    truncate_after_index: Optional[int] = None  # 截断索引，删除此索引之后的消息
    skip_user_message: bool = False  # 是否跳过追加用户消息（重新生成时使用）
    reasoning_effort: Optional[str] = None  # Reasoning effort: "low", "medium", "high"
    context_type: str = "chat"  # Context type: "chat" or "project"
    project_id: Optional[str] = None  # Project ID (required when context_type="project")
    use_web_search: bool = False  # Whether to use web search for this message
    search_query: Optional[str] = None  # Optional explicit search query


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    session_id: str
    response: str
    sources: Optional[List[SearchSource]] = None


class DeleteMessageRequest(BaseModel):
    """Request model for delete message endpoint."""
    session_id: str
    message_index: Optional[int] = None
    message_id: Optional[str] = None
    context_type: str = "chat"
    project_id: Optional[str] = None


class InsertSeparatorRequest(BaseModel):
    """Request model for insert separator endpoint."""
    session_id: str
    context_type: str = "chat"
    project_id: Optional[str] = None


class ClearMessagesRequest(BaseModel):
    """Request model for clear all messages endpoint."""
    session_id: str
    context_type: str = "chat"
    project_id: Optional[str] = None


class UpdateMessageRequest(BaseModel):
    """Request model for update message content endpoint."""
    session_id: str
    message_id: str
    content: str
    context_type: str = "chat"
    project_id: Optional[str] = None


class CompressContextRequest(BaseModel):
    """Request model for compress context endpoint."""
    session_id: str
    context_type: str = "chat"
    project_id: Optional[str] = None


class CompareRequest(BaseModel):
    """Request model for compare endpoint."""
    session_id: str
    message: str
    model_ids: List[str]  # composite IDs like "deepseek:deepseek-chat"
    attachments: Optional[List[Dict[str, Any]]] = None
    reasoning_effort: Optional[str] = None
    context_type: str = "chat"
    project_id: Optional[str] = None
    use_web_search: bool = False
    search_query: Optional[str] = None
    file_references: Optional[List[Dict[str, str]]] = None  # List of {path, project_id} for @file references


def get_agent_service() -> AgentService:
    """Dependency injection for AgentService."""
    storage = create_storage_with_project_resolver(settings.conversations_dir)
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
        request: ChatRequest with session_id, message, and context parameters

    Returns:
        ChatResponse with session_id and AI response

    Raises:
        404: Session not found
        400: Invalid context parameters
        500: Internal server error (agent failure)
    """
    # Validate context parameters
    if request.context_type == "project" and not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

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

        response, sources = await agent.process_message(
            request.session_id,
            request.message,
            context_type=request.context_type,
            project_id=request.project_id,
            use_web_search=request.use_web_search,
            search_query=request.search_query,
            file_references=request.file_references
        )

        print("=" * 80)
        print("✅ 消息处理完成")
        print(f"   AI 回复: {response[:100]}{'...' if len(response) > 100 else ''}")
        print("=" * 80)

        logger.info("=" * 80)
        logger.info("✅ 消息处理完成")
        logger.info(f"   AI 回复: {response[:100]}{'...' if len(response) > 100 else ''}")
        logger.info("=" * 80)

        return ChatResponse(session_id=request.session_id, response=response, sources=sources or None)
    except FileNotFoundError as e:
        print(f"❌ 会话未找到: {request.session_id}")
        logger.error(f"❌ 会话未找到: {request.session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        print(f"❌ 验证错误: {str(e)}")
        logger.error(f"❌ 验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
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
        request: ChatRequest with session_id, message, and context parameters

    Returns:
        StreamingResponse with Server-Sent Events

    Raises:
        404: Session not found
        400: Invalid context parameters
        500: Internal server error (agent failure)
    """
    # Validate context parameters
    if request.context_type == "project" and not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

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
                    request.truncate_after_index,
                    context_type=request.context_type,
                    project_id=request.project_id
                )

            # Check for group chat mode
            session_data = await agent.storage.get_session(
                request.session_id,
                context_type=request.context_type,
                project_id=request.project_id
            )
            group_assistants = session_data.get("group_assistants")
            group_mode = session_data.get("group_mode", "round_robin")

            if group_assistants and len(group_assistants) >= 2:
                # Group chat: process with multiple assistants
                stream_fn = agent.process_group_message_stream(
                    request.session_id,
                    request.message,
                    group_assistants=group_assistants,
                    group_mode=group_mode,
                    skip_user_append=request.skip_user_message,
                    reasoning_effort=request.reasoning_effort,
                    attachments=request.attachments,
                    context_type=request.context_type,
                    project_id=request.project_id,
                    use_web_search=request.use_web_search,
                    search_query=request.search_query,
                    file_references=request.file_references
                )
            else:
                # Single assistant: normal processing
                stream_fn = agent.process_message_stream(
                    request.session_id,
                    request.message,
                    skip_user_append=request.skip_user_message,
                    reasoning_effort=request.reasoning_effort,
                    attachments=request.attachments,
                    context_type=request.context_type,
                    project_id=request.project_id,
                    use_web_search=request.use_web_search,
                    search_query=request.search_query,
                    file_references=request.file_references
                )

            # Stream process messages
            async for chunk in stream_fn:
                # Check if chunk is a dict event (usage, user_message_id, assistant_message_id)
                if isinstance(chunk, dict):
                    # Forward dict events as-is
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
        except ValueError as e:
            print(f"❌ 验证错误: {str(e)}")
            logger.error(f"❌ 验证错误: {str(e)}")
            error_data = json.dumps({"error": str(e)})
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
    context_type: str = Query("chat", description="Session context: 'chat' or 'project'"),
    project_id: Optional[str] = Query(None, description="Project ID (required for project context)"),
    file_service: FileService = Depends(get_file_service)
):
    """Download a file attachment.

    Args:
        session_id: Session identifier
        message_index: Message index
        filename: Filename
        context_type: Context type ("chat" or "project")
        project_id: Project ID (required when context_type="project")

    Returns:
        File response

    Raises:
        404: File not found
        403: Access denied (path traversal attempt)
        400: Invalid context parameters
    """
    # Validate context parameters
    if context_type == "project" and not project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

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
        request: DeleteMessageRequest with session_id, context, and either message_id or message_index

    Returns:
        Success message

    Raises:
        404: Session not found
        400: Invalid message index or ID, or invalid context parameters
        500: Internal server error
    """
    # Validate context parameters
    if request.context_type == "project" and not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    # Prefer message_id if provided, fallback to message_index
    if request.message_id:
        logger.info(f"Delete message request: session={request.session_id[:16]}..., message_id={request.message_id}")
        try:
            await agent.storage.delete_message_by_id(
                request.session_id,
                request.message_id,
                context_type=request.context_type,
                project_id=request.project_id
            )
            return {"success": True, "message": "Message deleted"}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Delete message error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")
    elif request.message_index is not None:
        logger.info(f"Delete message request: session={request.session_id[:16]}..., index={request.message_index}")
        try:
            await agent.storage.delete_message(
                request.session_id,
                request.message_index,
                context_type=request.context_type,
                project_id=request.project_id
            )
            return {"success": True, "message": "Message deleted"}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
        except IndexError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Delete message error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Either message_id or message_index must be provided")


@router.put("/chat/message")
async def update_message(
    request: UpdateMessageRequest,
    agent: AgentService = Depends(get_agent_service)
):
    """Update the content of a specific message."""
    if request.context_type == "project" and not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(f"Update message request: session={request.session_id[:16]}..., message_id={request.message_id}")
    try:
        await agent.storage.update_message_content(
            request.session_id,
            request.message_id,
            request.content,
            context_type=request.context_type,
            project_id=request.project_id
        )
        return {"success": True, "message": "Message updated"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update message error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")


@router.post("/chat/separator")
async def insert_separator(
    request: InsertSeparatorRequest,
    agent: AgentService = Depends(get_agent_service)
):
    """
    Insert a context separator into conversation.

    Separators mark context boundaries - when LLM is called, only messages
    after the last separator will be included in the conversation history.

    Args:
        request: InsertSeparatorRequest with session_id and context parameters

    Returns:
        Success response with message_id

    Raises:
        404: Session not found
        400: Invalid context parameters
        500: Internal server error
    """
    # Validate context parameters
    if request.context_type == "project" and not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    try:
        message_id = await agent.storage.append_separator(
            request.session_id,
            context_type=request.context_type,
            project_id=request.project_id
        )
        return {"success": True, "message_id": message_id}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Insert separator error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Insert error: {str(e)}")


@router.post("/chat/clear")
async def clear_all_messages(
    request: ClearMessagesRequest,
    agent: AgentService = Depends(get_agent_service)
):
    """
    Clear all messages from the conversation.

    This will delete all messages and reset the conversation to empty state.

    Args:
        request: ClearMessagesRequest with session_id and context parameters

    Returns:
        Success response

    Raises:
        404: Session not found
        400: Invalid context parameters
        500: Internal server error
    """
    # Validate context parameters
    if request.context_type == "project" and not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    try:
        await agent.storage.clear_all_messages(
            request.session_id,
            context_type=request.context_type,
            project_id=request.project_id
        )
        return {"success": True, "message": "All messages cleared"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Clear messages error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Clear error: {str(e)}")


@router.post("/chat/compress")
async def compress_context(
    request: CompressContextRequest,
    agent: AgentService = Depends(get_agent_service)
):
    """Compress conversation context by summarizing messages via LLM.

    Streams the summary as SSE events, then appends it to the conversation.

    Args:
        request: CompressContextRequest with session_id and context parameters

    Returns:
        StreamingResponse with Server-Sent Events

    Raises:
        404: Session not found
        400: Invalid context parameters
        500: Internal server error
    """
    if request.context_type == "project" and not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    from ..services.compression_service import CompressionService
    compression_service = CompressionService(agent.storage)

    async def event_generator():
        try:
            async for chunk in compression_service.compress_context_stream(
                session_id=request.session_id,
                context_type=request.context_type,
                project_id=request.project_id,
            ):
                if isinstance(chunk, dict):
                    data = json.dumps(chunk, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                    continue

                data = json.dumps({"chunk": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

        except FileNotFoundError:
            error_data = json.dumps({"error": "Session not found"})
            yield f"data: {error_data}\n\n"
        except ValueError as e:
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"
        except Exception as e:
            logger.error(f"Compress context error: {str(e)}", exc_info=True)
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/chat/compare")
async def chat_compare(
    request: CompareRequest,
    agent: AgentService = Depends(get_agent_service)
):
    """Stream compare responses from multiple models.

    Sends the same context to all specified models simultaneously
    and returns a multiplexed SSE stream with model-tagged events.

    Args:
        request: CompareRequest with session_id, message, model_ids, etc.

    Returns:
        StreamingResponse with Server-Sent Events

    Raises:
        400: Invalid request (< 2 model_ids, invalid context params)
        404: Session not found
        500: Internal server error
    """
    if request.context_type == "project" and not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    if len(request.model_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 model_ids are required for comparison")

    logger.info(f"Compare request: session={request.session_id[:16]}..., models={request.model_ids}")

    async def event_generator():
        try:
            async for event in agent.process_compare_stream(
                request.session_id,
                request.message,
                request.model_ids,
                reasoning_effort=request.reasoning_effort,
                attachments=request.attachments,
                context_type=request.context_type,
                project_id=request.project_id,
                use_web_search=request.use_web_search,
                search_query=request.search_query,
                file_references=request.file_references,
            ):
                if isinstance(event, dict):
                    data = json.dumps(event, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                else:
                    data = json.dumps({"chunk": event}, ensure_ascii=False)
                    yield f"data: {data}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

        except FileNotFoundError:
            error_data = json.dumps({"error": "Session not found"})
            yield f"data: {error_data}\n\n"
        except ValueError as e:
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"
        except Exception as e:
            logger.error(f"Compare error: {str(e)}", exc_info=True)
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
