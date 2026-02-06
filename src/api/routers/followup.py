"""
Follow-up Questions API Router

Provides endpoints for configuring follow-up question generation.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import logging

from ..services.followup_service import FollowupService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/followup", tags=["followup"])


# Pydantic models
class FollowupConfigResponse(BaseModel):
    """Response model for follow-up configuration"""
    enabled: bool
    count: int
    model_id: str
    max_context_rounds: int
    timeout_seconds: int
    prompt_template: str


class FollowupConfigUpdate(BaseModel):
    """Request model for updating follow-up configuration"""
    enabled: Optional[bool] = None
    count: Optional[int] = Field(None, ge=0, le=5)
    model_id: Optional[str] = None
    max_context_rounds: Optional[int] = Field(None, ge=1, le=10)
    timeout_seconds: Optional[int] = Field(None, ge=5, le=60)
    prompt_template: Optional[str] = None


# Dependency: Get followup service instance
def get_followup_service() -> FollowupService:
    """Get FollowupService instance"""
    return FollowupService()


# Endpoints
@router.get("/config", response_model=FollowupConfigResponse)
async def get_config(
    service: FollowupService = Depends(get_followup_service)
):
    """Get current follow-up configuration"""
    try:
        config = service.config
        return FollowupConfigResponse(
            enabled=config.enabled,
            count=config.count,
            model_id=config.model_id,
            max_context_rounds=config.max_context_rounds,
            timeout_seconds=config.timeout_seconds,
            prompt_template=config.prompt_template
        )
    except Exception as e:
        logger.error(f"Failed to get followup config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: FollowupConfigUpdate,
    service: FollowupService = Depends(get_followup_service)
):
    """Update follow-up configuration"""
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
        logger.error(f"Failed to update followup config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
