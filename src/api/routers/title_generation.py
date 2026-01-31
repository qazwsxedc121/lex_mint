"""
Title Generation API Router

Provides endpoints for configuring and triggering title generation.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import logging

from ..services.title_generation_service import TitleGenerationService
from ..services.conversation_storage import ConversationStorage
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/title-generation", tags=["title-generation"])


# Pydantic models
class TitleGenerationConfigResponse(BaseModel):
    """Response model for title generation configuration"""
    enabled: bool
    trigger_threshold: int
    model_id: str
    prompt_template: str
    max_context_rounds: int
    timeout_seconds: int


class TitleGenerationConfigUpdate(BaseModel):
    """Request model for updating title generation configuration"""
    enabled: Optional[bool] = None
    trigger_threshold: Optional[int] = Field(None, ge=1, le=10)
    model_id: Optional[str] = None
    prompt_template: Optional[str] = None
    max_context_rounds: Optional[int] = Field(None, ge=1, le=10)
    timeout_seconds: Optional[int] = Field(None, ge=5, le=60)


class ManualGenerateRequest(BaseModel):
    """Request model for manual title generation"""
    session_id: str


# Dependency: Get title generation service instance
def get_title_service() -> TitleGenerationService:
    """Get TitleGenerationService instance"""
    storage = ConversationStorage(settings.conversations_dir)
    return TitleGenerationService(storage=storage)


# Endpoints
@router.get("/config", response_model=TitleGenerationConfigResponse)
async def get_config(
    service: TitleGenerationService = Depends(get_title_service)
):
    """Get current title generation configuration"""
    try:
        config = service.config
        return TitleGenerationConfigResponse(
            enabled=config.enabled,
            trigger_threshold=config.trigger_threshold,
            model_id=config.model_id,
            prompt_template=config.prompt_template,
            max_context_rounds=config.max_context_rounds,
            timeout_seconds=config.timeout_seconds
        )
    except Exception as e:
        logger.error(f"Failed to get title generation config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: TitleGenerationConfigUpdate,
    service: TitleGenerationService = Depends(get_title_service)
):
    """Update title generation configuration"""
    try:
        # Convert to dict, excluding None values
        update_dict = updates.model_dump(exclude_none=True)

        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        # Save to file
        service.save_config(update_dict)

        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update title generation config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_title(
    request: ManualGenerateRequest,
    service: TitleGenerationService = Depends(get_title_service)
):
    """Manually trigger title generation for a session"""
    try:
        # Call synchronously (await the result)
        title = await service.generate_title_async(request.session_id)

        if title:
            return {
                "message": "Title generated successfully",
                "title": title
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Title generation failed. Check server logs for details."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate title: {e}")
        raise HTTPException(status_code=500, detail=str(e))
