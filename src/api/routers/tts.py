"""
TTS API Router

Provides endpoint for text-to-speech synthesis.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
import logging

from edge_tts.exceptions import NoAudioReceived

from ..services.tts_service import TTSService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tts", tags=["tts"])

tts_service = TTSService()


class TTSSynthesizeRequest(BaseModel):
    """Request model for TTS synthesis"""
    text: str
    voice: Optional[str] = None
    rate: Optional[str] = None


@router.post("/synthesize")
async def synthesize(request: TTSSynthesizeRequest):
    """Synthesize text to speech audio.

    Returns audio/mpeg response with all audio bytes collected first,
    so errors are properly returned as HTTP error codes.
    """
    try:
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text is required")

        tts_service.config_service.reload_config()
        config = tts_service.config_service.config

        if not config.enabled:
            raise HTTPException(status_code=403, detail="TTS is disabled")

        audio_data = await tts_service.synthesize(request.text, request.voice, request.rate)

        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "no-cache",
            }
        )
    except HTTPException:
        raise
    except NoAudioReceived:
        logger.warning("Edge TTS returned no audio - voice may not support the given text")
        raise HTTPException(
            status_code=422,
            detail="No audio received. The voice may not support the given text content. Try a different voice."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
