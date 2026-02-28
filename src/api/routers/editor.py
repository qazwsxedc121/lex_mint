"""Editor-related API endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..services.editor_rewrite_service import EditorRewriteService
from ..services.flow_event_emitter import FlowEventEmitter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["editor"])


MAX_SELECTED_CHARS = 12000
MAX_CONTEXT_CHARS = 4000
MAX_INSTRUCTION_CHARS = 800
MAX_FILE_PATH_CHARS = 600
MAX_LANGUAGE_CHARS = 64


class RewriteRequest(BaseModel):
    """Request payload for inline rewrite streaming."""

    session_id: str = Field(min_length=1)
    selected_text: str = Field(min_length=1, max_length=MAX_SELECTED_CHARS)
    instruction: Optional[str] = Field(default=None, max_length=MAX_INSTRUCTION_CHARS)
    context_before: str = Field(default="", max_length=MAX_CONTEXT_CHARS)
    context_after: str = Field(default="", max_length=MAX_CONTEXT_CHARS)
    file_path: Optional[str] = Field(default=None, max_length=MAX_FILE_PATH_CHARS)
    language: Optional[str] = Field(default=None, max_length=MAX_LANGUAGE_CHARS)
    context_type: str = "project"
    project_id: Optional[str] = None


def get_editor_rewrite_service() -> EditorRewriteService:
    """Dependency injection for editor rewrite service."""

    return EditorRewriteService()


@router.post("/editor/rewrite")
async def rewrite_text(
    request: RewriteRequest,
    rewrite_service: EditorRewriteService = Depends(get_editor_rewrite_service),
):
    """Stream rewritten text for editor inline replacement."""

    if request.context_type != "project":
        raise HTTPException(status_code=400, detail="context_type must be 'project' for editor rewrite")
    if not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for project context")
    if not request.selected_text.strip():
        raise HTTPException(status_code=400, detail="selected_text cannot be empty")

    emitter = FlowEventEmitter(
        stream_id=str(uuid.uuid4()),
        conversation_id=request.session_id,
    )

    async def event_generator():
        started_payload = emitter.emit_started(context_type=request.context_type)
        yield f"data: {json.dumps(started_payload, ensure_ascii=False, default=str)}\n\n"
        try:
            async for chunk in rewrite_service.stream_rewrite(
                session_id=request.session_id,
                selected_text=request.selected_text,
                instruction=request.instruction,
                context_before=request.context_before,
                context_after=request.context_after,
                file_path=request.file_path,
                language=request.language,
                context_type=request.context_type,
                project_id=request.project_id,
            ):
                if not chunk:
                    continue
                text_payload = emitter.emit_text_delta(chunk)
                yield f"data: {json.dumps(text_payload, ensure_ascii=False, default=str)}\n\n"

            ended_payload = emitter.emit_ended()
            yield f"data: {json.dumps(ended_payload, ensure_ascii=False, default=str)}\n\n"

        except FileNotFoundError:
            error_payload = emitter.emit_error("Session not found")
            yield f"data: {json.dumps(error_payload, ensure_ascii=False, default=str)}\n\n"
        except ValueError as e:
            error_payload = emitter.emit_error(str(e))
            yield f"data: {json.dumps(error_payload, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            logger.error("Editor rewrite stream failed: %s", e, exc_info=True)
            error_payload = emitter.emit_error(str(e))
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
