"""Chat API endpoints."""

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from src.application.chat import ChatApplicationService
from src.application.chat.client_tool_call_coordinator import (
    get_client_tool_call_coordinator,
)
from src.application.flow.flow_event_emitter import FlowEventEmitter
from src.application.flow.flow_event_mapper import FlowEventMapper
from src.application.flow.flow_event_types import (
    REPLAY_FINISHED,
    RESUME_STARTED,
    TERMINAL_EVENT_TYPES,
)
from src.application.flow.flow_events import FlowEventStage
from src.application.flow.flow_stream_runtime import (
    FlowReplayCursorGoneError,
    FlowStreamContextMismatchError,
    FlowStreamNotFoundError,
    FlowStreamRuntime,
)
from src.application.flow.flow_stream_runtime_provider import get_flow_stream_runtime
from src.domain.models.search import SearchSource
from src.infrastructure.files.file_service import FileService

from ..dependencies import get_chat_application_service as get_shared_chat_application_service
from ..dependencies import get_file_service as get_shared_file_service

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
    attachments: list[dict[str, Any]] | None = (
        None  # List of {filename, size, mime_type, temp_path}
    )
    file_references: list[dict[str, str]] | None = (
        None  # List of {path, project_id} for @file references
    )
    truncate_after_index: int | None = None  # 截断索引，删除此索引之后的消息
    skip_user_message: bool = False  # 是否跳过追加用户消息（重新生成时使用）
    temporary_turn: bool = False  # Whether this turn should be ephemeral and non-persistent
    reasoning_effort: str | None = None  # Reasoning effort: "low", "medium", "high"
    context_type: str = "chat"  # Context type: "chat" or "project"
    project_id: str | None = None  # Project ID (required when context_type="project")
    active_file_path: str | None = None  # Active file path for project chat document tools
    active_file_hash: str | None = None  # Optional client-side content hash for active file
    use_web_search: bool = False  # Whether to use web search for this message
    search_query: str | None = None  # Optional explicit search query


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    session_id: str
    response: str
    sources: list[SearchSource] | None = None


class DeleteMessageRequest(BaseModel):
    """Request model for delete message endpoint."""

    session_id: str
    message_index: int | None = None
    message_id: str | None = None
    context_type: str = "chat"
    project_id: str | None = None


class InsertSeparatorRequest(BaseModel):
    """Request model for insert separator endpoint."""

    session_id: str
    context_type: str = "chat"
    project_id: str | None = None


class ClearMessagesRequest(BaseModel):
    """Request model for clear all messages endpoint."""

    session_id: str
    context_type: str = "chat"
    project_id: str | None = None


class UpdateMessageRequest(BaseModel):
    """Request model for update message content endpoint."""

    session_id: str
    message_id: str
    content: str
    context_type: str = "chat"
    project_id: str | None = None


class CompressContextRequest(BaseModel):
    """Request model for compress context endpoint."""

    session_id: str
    context_type: str = "chat"
    project_id: str | None = None


class CompareRequest(BaseModel):
    """Request model for compare endpoint."""

    session_id: str
    message: str
    model_ids: list[str]  # composite IDs like "deepseek:deepseek-chat"
    attachments: list[dict[str, Any]] | None = None
    reasoning_effort: str | None = None
    context_type: str = "chat"
    project_id: str | None = None
    use_web_search: bool = False
    search_query: str | None = None
    file_references: list[dict[str, str]] | None = (
        None  # List of {path, project_id} for @file references
    )


class ResumeStreamRequest(BaseModel):
    """Request model for resuming an existing stream."""

    session_id: str
    stream_id: str
    last_event_id: str
    context_type: str = "chat"
    project_id: str | None = None


class SubmitToolResultRequest(BaseModel):
    """Request model for submitting a client-executed tool result."""

    session_id: str
    tool_call_id: str
    name: str
    result: str


def get_chat_application_service() -> ChatApplicationService:
    """Dependency injection for chat application entry service."""
    return get_shared_chat_application_service()


def get_file_service() -> FileService:
    """Dependency injection for FileService."""
    return get_shared_file_service()


def _is_terminal_payload(payload: dict[str, Any]) -> bool:
    flow_event = payload.get("flow_event")
    if isinstance(flow_event, dict):
        if flow_event.get("event_type") in TERMINAL_EVENT_TYPES:
            return True
    return payload.get("done") is True or "error" in payload


async def _build_stream_fn(
    request: ChatRequest,
    agent: ChatApplicationService,
):
    if request.truncate_after_index is not None:
        print(f"[SSE] Truncating messages to index {request.truncate_after_index}")
        logger.info(f"[SSE] Truncating messages to index {request.truncate_after_index}")
        await agent.truncate_messages_after(
            session_id=request.session_id,
            keep_until_index=request.truncate_after_index,
            context_type=request.context_type,
            project_id=request.project_id,
        )

    return agent.process_chat_stream(
        request.session_id,
        request.message,
        skip_user_append=request.skip_user_message,
        temporary_turn=request.temporary_turn,
        reasoning_effort=request.reasoning_effort,
        attachments=request.attachments,
        context_type=request.context_type,
        project_id=request.project_id,
        use_web_search=request.use_web_search,
        search_query=request.search_query,
        file_references=request.file_references,
        active_file_path=request.active_file_path,
        active_file_hash=request.active_file_hash,
    )


async def _run_chat_stream_producer(
    *,
    request: ChatRequest,
    agent: ChatApplicationService,
    runtime: FlowStreamRuntime,
    stream_id: str,
) -> None:
    mapper = FlowEventMapper(
        stream_id=stream_id,
        conversation_id=request.session_id,
        seq_provider=lambda: runtime.next_seq(stream_id),
    )

    try:
        print("[SSE] Starting stream processing...")
        logger.info("[SSE] Starting stream processing...")
        runtime.append_payload(
            stream_id,
            mapper.make_stream_started_payload(context_type=request.context_type),
        )

        stream_fn = await _build_stream_fn(request, agent)
        async for chunk in stream_fn:
            runtime.append_payload(stream_id, mapper.to_sse_payload(chunk))

        runtime.append_payload(stream_id, mapper.to_sse_payload({"done": True}))

        print("=" * 80)
        print("[OK] Stream processing complete")
        print("=" * 80)
        logger.info("=" * 80)
        logger.info("[OK] Stream processing complete")
        logger.info("=" * 80)

    except FileNotFoundError:
        print(f"❌ 会话未找到: {request.session_id}")
        logger.error(f"❌ 会话未找到: {request.session_id}")
        runtime.append_payload(stream_id, mapper.to_sse_payload({"error": "Session not found"}))
    except ValueError as e:
        print(f"❌ 验证错误: {str(e)}")
        logger.error(f"❌ 验证错误: {str(e)}")
        runtime.append_payload(stream_id, mapper.to_sse_payload({"error": str(e)}))
    except Exception as e:
        print(f"❌ Agent 错误: {str(e)}")
        logger.error(f"❌ Agent 错误: {str(e)}", exc_info=True)
        runtime.append_payload(stream_id, mapper.to_sse_payload({"error": str(e)}))


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest, agent: ChatApplicationService = Depends(get_chat_application_service)
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
    print("📨 收到聊天请求")
    print(f"   Session ID: {request.session_id[:16]}...")
    print(f"   用户消息: {request.message[:100]}{'...' if len(request.message) > 100 else ''}")
    print("=" * 80)

    logger.info("=" * 80)
    logger.info("📨 收到聊天请求")
    logger.info(f"   Session ID: {request.session_id[:16]}...")
    logger.info(
        f"   用户消息: {request.message[:100]}{'...' if len(request.message) > 100 else ''}"
    )
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
            file_references=request.file_references,
            active_file_path=request.active_file_path,
            active_file_hash=request.active_file_hash,
        )

        print("=" * 80)
        print("✅ 消息处理完成")
        print(f"   AI 回复: {response[:100]}{'...' if len(response) > 100 else ''}")
        print("=" * 80)

        logger.info("=" * 80)
        logger.info("✅ 消息处理完成")
        logger.info(f"   AI 回复: {response[:100]}{'...' if len(response) > 100 else ''}")
        logger.info("=" * 80)

        response_sources: list[SearchSource] | None = None
        if sources:
            response_sources = []
            for source in sources:
                try:
                    response_sources.append(SearchSource.model_validate(source))
                except Exception:
                    continue
        return ChatResponse(
            session_id=request.session_id, response=response, sources=response_sources
        )
    except FileNotFoundError:
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
    agent: ChatApplicationService = Depends(get_chat_application_service),
    runtime: FlowStreamRuntime = Depends(get_flow_stream_runtime),
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
    print("📨 收到流式聊天请求")
    print(f"   Session ID: {request.session_id[:16]}...")
    print(f"   用户消息: {request.message[:100]}{'...' if len(request.message) > 100 else ''}")
    print("=" * 80)

    logger.info("=" * 80)
    logger.info("📨 收到流式聊天请求")
    logger.info(f"   Session ID: {request.session_id[:16]}...")
    logger.info(
        f"   用户消息: {request.message[:100]}{'...' if len(request.message) > 100 else ''}"
    )
    logger.info("=" * 80)

    stream_id = str(uuid.uuid4())
    try:
        runtime.create_stream(
            stream_id=stream_id,
            conversation_id=request.session_id,
            context_type=request.context_type,
            project_id=request.project_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=503, detail="flow stream runtime overloaded")

    subscriber_id, queue = runtime.subscribe(stream_id)
    asyncio.create_task(
        _run_chat_stream_producer(
            request=request,
            agent=agent,
            runtime=runtime,
            stream_id=stream_id,
        )
    )

    async def event_generator():
        """Generate SSE data stream from runtime queue."""
        try:
            while True:
                payload = await queue.get()
                yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                if _is_terminal_payload(payload):
                    return
        finally:
            runtime.unsubscribe(stream_id, subscriber_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@router.post("/chat/stream/resume")
async def resume_chat_stream(
    request: ResumeStreamRequest,
    runtime: FlowStreamRuntime = Depends(get_flow_stream_runtime),
):
    """Resume an existing chat stream from a known flow_event cursor."""
    if request.context_type == "project" and not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    try:
        subscriber_id, queue, replay_payloads = runtime.resume_subscribe(
            stream_id=request.stream_id,
            last_event_id=request.last_event_id,
            conversation_id=request.session_id,
            context_type=request.context_type,
            project_id=request.project_id,
        )
    except FlowStreamNotFoundError:
        raise HTTPException(
            status_code=404, detail={"code": "stream_not_found", "message": "stream not found"}
        )
    except FlowReplayCursorGoneError:
        raise HTTPException(
            status_code=410,
            detail={
                "code": "replay_cursor_gone",
                "message": "last_event_id is outside replay window",
            },
        )
    except FlowStreamContextMismatchError:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stream_context_mismatch",
                "message": "stream context does not match request",
            },
        )

    async def event_generator():
        """Replay cached events and then continue with live queue."""
        terminal_seen = False
        resume_emitter = FlowEventEmitter(
            stream_id=request.stream_id,
            conversation_id=request.session_id,
            seq_provider=lambda: runtime.next_seq(request.stream_id),
        )
        try:
            resume_started = resume_emitter.emit(
                event_type=RESUME_STARTED,
                stage=FlowEventStage.TRANSPORT,
                payload={"last_event_id": request.last_event_id},
            )
            yield f"data: {json.dumps(resume_started, ensure_ascii=False, default=str)}\n\n"

            for payload in replay_payloads:
                yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                if _is_terminal_payload(payload):
                    terminal_seen = True
                    return

            replay_finished = resume_emitter.emit(
                event_type=REPLAY_FINISHED,
                stage=FlowEventStage.TRANSPORT,
                payload={"replayed_count": len(replay_payloads)},
            )
            yield f"data: {json.dumps(replay_finished, ensure_ascii=False, default=str)}\n\n"

            if terminal_seen:
                return

            if runtime.get_stream(request.stream_id).done:
                return

            while True:
                payload = await queue.get()
                yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                if _is_terminal_payload(payload):
                    return
        finally:
            runtime.unsubscribe(request.stream_id, subscriber_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/tool-result")
async def submit_chat_tool_result(request: SubmitToolResultRequest):
    """Submit result for a client-executed tool call (for example pyodide)."""
    if not request.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required")
    if not request.tool_call_id.strip():
        raise HTTPException(status_code=400, detail="tool_call_id is required")

    coordinator = get_client_tool_call_coordinator()
    await coordinator.submit_result(
        session_id=request.session_id.strip(),
        tool_call_id=request.tool_call_id.strip(),
        result=request.result,
    )
    return {"success": True}


@router.post("/chat/upload")
async def upload_file(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
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
    project_id: str | None = Query(None, description="Project ID (required for project context)"),
    file_service: FileService = Depends(get_file_service),
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

    logger.info(
        f"File download request: session={session_id[:16]}..., index={message_index}, file={filename}"
    )

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

    return FileResponse(filepath, media_type="application/octet-stream", filename=filename)


@router.delete("/chat/message")
async def delete_message(
    request: DeleteMessageRequest,
    agent: ChatApplicationService = Depends(get_chat_application_service),
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
        logger.info(
            f"Delete message request: session={request.session_id[:16]}..., message_id={request.message_id}"
        )
        try:
            await agent.delete_message(
                session_id=request.session_id,
                message_id=request.message_id,
                context_type=request.context_type,
                project_id=request.project_id,
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
        logger.info(
            f"Delete message request: session={request.session_id[:16]}..., index={request.message_index}"
        )
        try:
            await agent.delete_message(
                session_id=request.session_id,
                message_index=request.message_index,
                context_type=request.context_type,
                project_id=request.project_id,
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
        raise HTTPException(
            status_code=400, detail="Either message_id or message_index must be provided"
        )


@router.put("/chat/message")
async def update_message(
    request: UpdateMessageRequest,
    agent: ChatApplicationService = Depends(get_chat_application_service),
):
    """Update the content of a specific message."""
    if request.context_type == "project" and not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")

    logger.info(
        f"Update message request: session={request.session_id[:16]}..., message_id={request.message_id}"
    )
    try:
        await agent.update_message_content(
            session_id=request.session_id,
            message_id=request.message_id,
            content=request.content,
            context_type=request.context_type,
            project_id=request.project_id,
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
    agent: ChatApplicationService = Depends(get_chat_application_service),
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
        message_id = await agent.append_separator(
            session_id=request.session_id,
            context_type=request.context_type,
            project_id=request.project_id,
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
    agent: ChatApplicationService = Depends(get_chat_application_service),
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
        await agent.clear_all_messages(
            session_id=request.session_id,
            context_type=request.context_type,
            project_id=request.project_id,
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
    agent: ChatApplicationService = Depends(get_chat_application_service),
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

    mapper = FlowEventMapper(
        stream_id=str(uuid.uuid4()),
        conversation_id=request.session_id,
    )

    async def event_generator():
        started_payload = mapper.make_stream_started_payload(context_type=request.context_type)
        yield f"data: {json.dumps(started_payload, ensure_ascii=False, default=str)}\n\n"
        try:
            async for chunk in agent.compress_context_stream(
                session_id=request.session_id,
                context_type=request.context_type,
                project_id=request.project_id,
            ):
                if isinstance(chunk, dict):
                    event_type = str(chunk.get("type") or "")
                    if event_type and event_type not in {"compression_complete", "error"}:
                        mapped_payload = mapper.to_sse_payload(
                            {"error": f"unsupported compression stream event type: {event_type}"}
                        )
                    else:
                        mapped_payload = mapper.to_sse_payload(chunk)
                else:
                    mapped_payload = mapper.to_sse_payload(chunk)
                yield f"data: {json.dumps(mapped_payload, ensure_ascii=False, default=str)}\n\n"
                if _is_terminal_payload(mapped_payload):
                    return

            ended_payload = mapper.to_sse_payload({"done": True})
            yield f"data: {json.dumps(ended_payload, ensure_ascii=False, default=str)}\n\n"

        except FileNotFoundError:
            error_payload = mapper.to_sse_payload({"error": "Session not found"})
            yield f"data: {json.dumps(error_payload, ensure_ascii=False, default=str)}\n\n"
        except ValueError as e:
            error_payload = mapper.to_sse_payload({"error": str(e)})
            yield f"data: {json.dumps(error_payload, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            logger.error(f"Compress context error: {str(e)}", exc_info=True)
            error_payload = mapper.to_sse_payload({"error": str(e)})
            yield f"data: {json.dumps(error_payload, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/compare")
async def chat_compare(
    request: CompareRequest, agent: ChatApplicationService = Depends(get_chat_application_service)
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
        raise HTTPException(
            status_code=400, detail="At least 2 model_ids are required for comparison"
        )

    logger.info(
        f"Compare request: session={request.session_id[:16]}..., models={request.model_ids}"
    )
    mapper = FlowEventMapper(
        stream_id=str(uuid.uuid4()),
        conversation_id=request.session_id,
    )

    async def event_generator():
        started_payload = mapper.make_stream_started_payload(context_type=request.context_type)
        yield f"data: {json.dumps(started_payload, ensure_ascii=False, default=str)}\n\n"
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
                mapped_payload = mapper.to_sse_payload(event)
                yield f"data: {json.dumps(mapped_payload, ensure_ascii=False, default=str)}\n\n"
                if _is_terminal_payload(mapped_payload):
                    return

            ended_payload = mapper.to_sse_payload({"done": True})
            yield f"data: {json.dumps(ended_payload, ensure_ascii=False, default=str)}\n\n"

        except FileNotFoundError:
            error_payload = mapper.to_sse_payload({"error": "Session not found"})
            yield f"data: {json.dumps(error_payload, ensure_ascii=False, default=str)}\n\n"
        except ValueError as e:
            error_payload = mapper.to_sse_payload({"error": str(e)})
            yield f"data: {json.dumps(error_payload, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            logger.error(f"Compare error: {str(e)}", exc_info=True)
            error_payload = mapper.to_sse_payload({"error": str(e)})
            yield f"data: {json.dumps(error_payload, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
