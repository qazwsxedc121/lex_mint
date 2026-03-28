"""
Translation API Router

Provides streaming translation endpoint.
"""

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.application.flow.flow_event_emitter import FlowEventEmitter
from src.application.flow.flow_event_types import (
    LANGUAGE_DETECTED,
    STREAM_ERROR,
    TRANSLATION_COMPLETED,
)
from src.application.flow.flow_events import FlowEventStage
from src.infrastructure.llm.language_detection_service import LanguageDetectionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["translation"])


class TranslateRequest(BaseModel):
    """Request model for translation endpoint."""

    text: str
    target_language: str | None = None
    model_id: str | None = None
    use_input_target_language: bool = False
    auto_detect_language: bool = True


class DetectLanguageRequest(BaseModel):
    """Request model for language detection endpoint."""

    text: str


class DetectLanguageResponse(BaseModel):
    """Response model for language detection endpoint."""

    language: str | None = None
    confidence: float | None = None
    detector: str


@router.post("/translate/detect-language", response_model=DetectLanguageResponse)
async def detect_language(request: DetectLanguageRequest):
    """Detect source language from a piece of text."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    language, confidence, detector = LanguageDetectionService.detect_language(request.text)
    normalized_language = LanguageDetectionService.normalize_language_hint(language)
    return DetectLanguageResponse(
        language=normalized_language,
        confidence=confidence,
        detector=detector,
    )


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

    from src.application.translation.translation_service import TranslationService

    translation_service = TranslationService()
    emitter = FlowEventEmitter(stream_id=str(uuid.uuid4()))

    async def event_generator():
        started_payload = emitter.emit_started(context_type="translation")
        yield f"data: {json.dumps(started_payload, ensure_ascii=False, default=str)}\n\n"
        try:
            async for chunk in translation_service.translate_stream(
                text=request.text,
                target_language=request.target_language,
                model_id=request.model_id,
                use_input_target_language=request.use_input_target_language,
                auto_detect_language=request.auto_detect_language,
            ):
                if isinstance(chunk, dict):
                    event_type = str(chunk.get("type") or "")
                    if event_type == "language_detected":
                        payload = emitter.emit(
                            event_type=LANGUAGE_DETECTED,
                            stage=FlowEventStage.META,
                            payload={
                                "language": chunk.get("language"),
                                "confidence": chunk.get("confidence"),
                                "detector": chunk.get("detector"),
                            },
                        )
                    elif event_type == "translation_complete":
                        payload = emitter.emit(
                            event_type=TRANSLATION_COMPLETED,
                            stage=FlowEventStage.META,
                            payload={
                                "detected_source_language": chunk.get("detected_source_language"),
                                "detected_source_confidence": chunk.get(
                                    "detected_source_confidence"
                                ),
                                "effective_target_language": chunk.get("effective_target_language"),
                            },
                        )
                    elif event_type == "error":
                        payload = emitter.emit_error(
                            str(chunk.get("error") or "translation stream error")
                        )
                    else:
                        payload = emitter.emit_error(
                            f"unsupported translation stream event type: {event_type}"
                        )
                    yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                    flow_event = payload.get("flow_event")
                    if (
                        isinstance(flow_event, dict)
                        and flow_event.get("event_type") == STREAM_ERROR
                    ):
                        return
                    continue

                text_payload = emitter.emit_text_delta(str(chunk))
                yield f"data: {json.dumps(text_payload, ensure_ascii=False, default=str)}\n\n"

            ended_payload = emitter.emit_ended()
            yield f"data: {json.dumps(ended_payload, ensure_ascii=False, default=str)}\n\n"

        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
            error_payload = emitter.emit_error(str(e))
            yield f"data: {json.dumps(error_payload, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
