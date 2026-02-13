"""File reference config API router."""

from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..services.file_reference_config_service import FileReferenceConfigService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/file-reference", tags=["file-reference"])


class FileReferenceConfigResponse(BaseModel):
    """Response model for file reference configuration."""

    ui_preview_max_chars: int
    ui_preview_max_lines: int
    injection_preview_max_chars: int
    injection_preview_max_lines: int
    chunk_size: int
    max_chunks: int
    total_budget_chars: int


class FileReferenceConfigUpdate(BaseModel):
    """Update payload for file reference configuration."""

    ui_preview_max_chars: Optional[int] = Field(None, ge=100, le=10000)
    ui_preview_max_lines: Optional[int] = Field(None, ge=1, le=300)
    injection_preview_max_chars: Optional[int] = Field(None, ge=100, le=5000)
    injection_preview_max_lines: Optional[int] = Field(None, ge=1, le=500)
    chunk_size: Optional[int] = Field(None, ge=200, le=20000)
    max_chunks: Optional[int] = Field(None, ge=1, le=50)
    total_budget_chars: Optional[int] = Field(None, ge=1000, le=500000)


def get_file_reference_config_service() -> FileReferenceConfigService:
    return FileReferenceConfigService()


@router.get("/config", response_model=FileReferenceConfigResponse)
async def get_config(
    service: FileReferenceConfigService = Depends(get_file_reference_config_service),
):
    """Get current file reference configuration."""
    try:
        cfg = service.config
        return FileReferenceConfigResponse(
            ui_preview_max_chars=cfg.ui_preview_max_chars,
            ui_preview_max_lines=cfg.ui_preview_max_lines,
            injection_preview_max_chars=cfg.injection_preview_max_chars,
            injection_preview_max_lines=cfg.injection_preview_max_lines,
            chunk_size=cfg.chunk_size,
            max_chunks=cfg.max_chunks,
            total_budget_chars=cfg.total_budget_chars,
        )
    except Exception as e:
        logger.error("Failed to get file reference config: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: FileReferenceConfigUpdate,
    service: FileReferenceConfigService = Depends(get_file_reference_config_service),
):
    """Update file reference configuration."""
    try:
        update_dict = updates.model_dump(exclude_none=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        service.save_config(update_dict)
        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update file reference config: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

