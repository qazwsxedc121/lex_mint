"""
TTS Config API Router

Provides endpoints for configuring text-to-speech and listing available voices.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

import edge_tts

from ..services.tts_config_service import TTSConfigService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tts", tags=["tts"])


# Pydantic models
class TTSConfigResponse(BaseModel):
    """Response model for TTS configuration"""
    enabled: bool
    voice: str
    voice_zh: str
    rate: str
    volume: str
    max_text_length: int


class TTSConfigUpdate(BaseModel):
    """Request model for updating TTS configuration"""
    enabled: Optional[bool] = None
    voice: Optional[str] = None
    voice_zh: Optional[str] = None
    rate: Optional[str] = None
    volume: Optional[str] = None
    max_text_length: Optional[int] = Field(None, ge=100, le=100000)


class VoiceInfo(BaseModel):
    """Voice information"""
    ShortName: str
    Locale: str
    Gender: str


# Dependency
def get_tts_config_service() -> TTSConfigService:
    """Get TTSConfigService instance"""
    return TTSConfigService()


# Endpoints
@router.get("/config", response_model=TTSConfigResponse)
async def get_config(
    service: TTSConfigService = Depends(get_tts_config_service)
):
    """Get current TTS configuration"""
    try:
        config = service.config
        return TTSConfigResponse(
            enabled=config.enabled,
            voice=config.voice,
            voice_zh=config.voice_zh,
            rate=config.rate,
            volume=config.volume,
            max_text_length=config.max_text_length,
        )
    except Exception as e:
        logger.error(f"Failed to get TTS config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: TTSConfigUpdate,
    service: TTSConfigService = Depends(get_tts_config_service)
):
    """Update TTS configuration"""
    try:
        update_dict = updates.model_dump(exclude_none=True)

        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        service.save_config(update_dict)

        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update TTS config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voices", response_model=List[VoiceInfo])
async def list_voices():
    """List available TTS voices from Edge TTS"""
    try:
        voices = await edge_tts.list_voices()
        return [
            VoiceInfo(
                ShortName=v["ShortName"],
                Locale=v["Locale"],
                Gender=v["Gender"],
            )
            for v in voices
        ]
    except Exception as e:
        logger.error(f"Failed to list TTS voices: {e}")
        raise HTTPException(status_code=500, detail=str(e))
