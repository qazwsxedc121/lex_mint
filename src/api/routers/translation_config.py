"""
Translation Config API Router

Provides endpoints for configuring translation.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import logging

from ..services.translation_config_service import TranslationConfigService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/translation", tags=["translation"])


# Pydantic models
class TranslationConfigResponse(BaseModel):
    """Response model for translation configuration"""
    enabled: bool
    target_language: str
    input_target_language: str
    model_id: str
    temperature: float
    timeout_seconds: int
    prompt_template: str


class TranslationConfigUpdate(BaseModel):
    """Request model for updating translation configuration"""
    enabled: Optional[bool] = None
    target_language: Optional[str] = None
    input_target_language: Optional[str] = None
    model_id: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    timeout_seconds: Optional[int] = Field(None, ge=10, le=300)
    prompt_template: Optional[str] = None


# Dependency
def get_translation_config_service() -> TranslationConfigService:
    """Get TranslationConfigService instance"""
    return TranslationConfigService()


# Endpoints
@router.get("/config", response_model=TranslationConfigResponse)
async def get_config(
    service: TranslationConfigService = Depends(get_translation_config_service)
):
    """Get current translation configuration"""
    try:
        config = service.config
        return TranslationConfigResponse(
            enabled=config.enabled,
            target_language=config.target_language,
            input_target_language=config.input_target_language,
            model_id=config.model_id,
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
            prompt_template=config.prompt_template,
        )
    except Exception as e:
        logger.error(f"Failed to get translation config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: TranslationConfigUpdate,
    service: TranslationConfigService = Depends(get_translation_config_service)
):
    """Update translation configuration"""
    try:
        update_dict = updates.model_dump(exclude_none=True)

        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        service.save_config(update_dict)

        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update translation config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
