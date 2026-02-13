"""
Follow-up Questions API Router

Provides endpoints for configuring follow-up question generation.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

from ..services.followup_service import FollowupService
from ..services.conversation_storage import ConversationStorage, create_storage_with_project_resolver
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/followup", tags=["followup"])


def get_storage() -> ConversationStorage:
    return create_storage_with_project_resolver(settings.conversations_dir)


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


@router.post("/generate", response_model=dict)
async def generate_followups(
    session_id: str = Query(..., description="Session ID"),
    context_type: str = Query("chat", description="Session context"),
    project_id: Optional[str] = Query(None, description="Project ID"),
    service: FollowupService = Depends(get_followup_service),
    storage: ConversationStorage = Depends(get_storage),
):
    """Generate follow-up questions for an existing session on demand."""
    try:
        session = await storage.get_session(session_id, context_type=context_type, project_id=project_id)
        messages = session['state']['messages']
        if not messages:
            return {"questions": []}

        questions = await service.generate_followups_async(messages)
        return {"questions": questions}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    except Exception as e:
        logger.error(f"Failed to generate follow-ups: {e}")
        raise HTTPException(status_code=500, detail=str(e))
