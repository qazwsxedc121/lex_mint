"""Chat folder management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
import logging

from ..services.folder_service import FolderService, Folder
from ..services.conversation_storage import ConversationStorage, create_storage_with_project_resolver
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/folders", tags=["folders"])


class CreateFolderRequest(BaseModel):
    """Create folder request"""
    name: str


class UpdateFolderRequest(BaseModel):
    """Update folder request"""
    name: str


class UpdateSessionFolderRequest(BaseModel):
    """Update session folder request"""
    folder_id: Optional[str] = None  # None to remove from folder


class ReorderFolderRequest(BaseModel):
    """Reorder folder request"""
    order: int


def get_folder_service() -> FolderService:
    """Dependency injection for FolderService."""
    return FolderService()


def get_storage() -> ConversationStorage:
    """Dependency injection for ConversationStorage."""
    return create_storage_with_project_resolver(settings.conversations_dir)


@router.get("", response_model=List[Folder])
async def list_folders(
    service: FolderService = Depends(get_folder_service)
):
    """
    List all chat folders ordered by order field.

    Returns:
        List of folders
    """
    try:
        folders = await service.list_folders()
        return folders
    except Exception as e:
        logger.error(f"Error listing folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Folder, status_code=201)
async def create_folder(
    request: CreateFolderRequest,
    service: FolderService = Depends(get_folder_service)
):
    """
    Create a new folder.

    Args:
        request: Folder creation data

    Returns:
        Created folder
    """
    try:
        folder = await service.create_folder(name=request.name)
        return folder
    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{folder_id}", response_model=Folder)
async def update_folder(
    folder_id: str,
    request: UpdateFolderRequest,
    service: FolderService = Depends(get_folder_service)
):
    """
    Update folder name.

    Args:
        folder_id: Folder ID
        request: Update data

    Returns:
        Updated folder

    Raises:
        404: Folder not found
    """
    try:
        folder = await service.update_folder(folder_id=folder_id, name=request.name)
        return folder
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: str,
    service: FolderService = Depends(get_folder_service),
    storage: ConversationStorage = Depends(get_storage)
):
    """
    Delete a folder.

    Sessions in this folder will be moved to ungrouped (folder_id set to null).

    Args:
        folder_id: Folder ID

    Raises:
        404: Folder not found
    """
    try:
        # First, remove folder assignment from all sessions
        # Get all chat sessions
        sessions = await storage.list_sessions(context_type="chat")

        # Update sessions that belong to this folder
        for session in sessions:
            if session.get("folder_id") == folder_id:
                try:
                    await storage.update_session_folder(
                        session_id=session["session_id"],
                        folder_id=None,
                        context_type="chat"
                    )
                except Exception as e:
                    logger.warning(f"Failed to clear folder_id for session {session['session_id']}: {e}")

        # Delete the folder
        await service.delete_folder(folder_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{folder_id}/order", response_model=Folder)
async def reorder_folder(
    folder_id: str,
    request: ReorderFolderRequest,
    service: FolderService = Depends(get_folder_service)
):
    """
    Reorder a folder to a new position.

    Args:
        folder_id: Folder ID
        request: Reorder data containing new order position

    Returns:
        Updated folder

    Raises:
        404: Folder not found
        400: Invalid order value
    """
    try:
        folder = await service.reorder_folder(folder_id=folder_id, new_order=request.order)
        return folder
    except ValueError as e:
        # Check if it's a "not found" error or "invalid order" error
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Error reordering folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))
