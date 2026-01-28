"""
Assistant management API endpoints

CRUD operations for AI assistant configurations
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from ..models.assistant_config import (
    Assistant,
    AssistantCreate,
    AssistantUpdate,
)
from ..services.assistant_config_service import AssistantConfigService
from ..services.model_config_service import ModelConfigService

router = APIRouter(prefix="/api/assistants", tags=["assistants"])


def get_assistant_service() -> AssistantConfigService:
    """Dependency injection: get assistant configuration service instance"""
    return AssistantConfigService(model_service=ModelConfigService())


# ==================== Assistant Management ====================

@router.get("", response_model=List[Assistant])
async def list_assistants(service: AssistantConfigService = Depends(get_assistant_service)):
    """Get all assistants list"""
    return await service.get_assistants()


@router.get("/{assistant_id}", response_model=Assistant)
async def get_assistant(
    assistant_id: str,
    service: AssistantConfigService = Depends(get_assistant_service)
):
    """
    Get specified assistant details

    Args:
        assistant_id: Assistant ID
    """
    assistant = await service.get_assistant(assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail=f"Assistant '{assistant_id}' not found")
    return assistant


@router.post("", status_code=201)
async def create_assistant(
    assistant_data: AssistantCreate,
    service: AssistantConfigService = Depends(get_assistant_service)
):
    """Create new assistant"""
    try:
        # Create Assistant object
        assistant = Assistant(**assistant_data.model_dump())
        await service.add_assistant(assistant)
        return {"message": "Assistant created successfully", "id": assistant_data.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{assistant_id}")
async def update_assistant(
    assistant_id: str,
    assistant_update: AssistantUpdate,
    service: AssistantConfigService = Depends(get_assistant_service)
):
    """
    Update assistant information

    Only updates fields that are provided (partial update)
    """
    try:
        # Get existing assistant
        existing = await service.get_assistant(assistant_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Assistant '{assistant_id}' not found")

        # Merge updates (only update provided fields)
        updated_data = existing.model_dump()
        for field, value in assistant_update.model_dump(exclude_unset=True).items():
            if value is not None:
                updated_data[field] = value

        # Create updated Assistant object
        updated_assistant = Assistant(**updated_data)
        await service.update_assistant(assistant_id, updated_assistant)

        return {"message": "Assistant updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{assistant_id}")
async def delete_assistant(
    assistant_id: str,
    service: AssistantConfigService = Depends(get_assistant_service)
):
    """Delete assistant (cannot delete default assistant)"""
    try:
        await service.delete_assistant(assistant_id)
        return {"message": "Assistant deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Default Assistant ====================

@router.get("/default/id")
async def get_default_assistant_id(service: AssistantConfigService = Depends(get_assistant_service)):
    """Get default assistant ID"""
    default_id = await service.get_default_assistant_id()
    return {"default_assistant_id": default_id}


@router.get("/default/assistant", response_model=Assistant)
async def get_default_assistant(service: AssistantConfigService = Depends(get_assistant_service)):
    """Get default assistant details"""
    try:
        return await service.get_default_assistant()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/default/{assistant_id}")
async def set_default_assistant(
    assistant_id: str,
    service: AssistantConfigService = Depends(get_assistant_service)
):
    """Set default assistant"""
    try:
        await service.set_default_assistant(assistant_id)
        return {"message": "Default assistant updated successfully", "default_assistant_id": assistant_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
