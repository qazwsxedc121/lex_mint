"""
Translation API Router

Provides streaming translation endpoint.
"""
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["translation"])


class TranslateRequest(BaseModel):
    """Request model for translation endpoint."""
    text: str
    target_language: Optional[str] = None
    model_id: Optional[str] = None
    use_input_target_language: bool = False


@router.post("/translate")
async def translate_text(request: TranslateRequest):
    """Translate text via LLM streaming.

    Streams translated text as SSE events.

    Args:
        request: TranslateRequest with text and optional overrides

    Returns:
        StreamingResponse with Server-Sent Events
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    from ..services.translation_service import TranslationService
    translation_service = TranslationService()

    async def event_generator():
        try:
            async for chunk in translation_service.translate_stream(
                text=request.text,
                target_language=request.target_language,
                model_id=request.model_id,
                use_input_target_language=request.use_input_target_language,
            ):
                if isinstance(chunk, dict):
                    data = json.dumps(chunk, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                    continue

                data = json.dumps({"chunk": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
