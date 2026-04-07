"""Code execution config API router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.routers.service_protocols import ConfigSaveServiceLike
from src.infrastructure.config.code_execution_config_service import CodeExecutionConfigService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/code-execution", tags=["code-execution"])


class CodeExecutionConfigResponse(BaseModel):
    enable_server_side_tool_execution: bool


class CodeExecutionConfigUpdate(BaseModel):
    enable_server_side_tool_execution: bool | None = None


def get_code_execution_config_service() -> CodeExecutionConfigService:
    return CodeExecutionConfigService()


@router.get("/config", response_model=CodeExecutionConfigResponse)
async def get_config(service: ConfigSaveServiceLike = Depends(get_code_execution_config_service)):
    try:
        config = service.config
        return CodeExecutionConfigResponse(
            enable_server_side_tool_execution=bool(config.enable_server_side_tool_execution)
        )
    except Exception as e:
        logger.error("Failed to get code execution config: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: CodeExecutionConfigUpdate,
    service: ConfigSaveServiceLike = Depends(get_code_execution_config_service),
):
    try:
        update_dict = updates.model_dump(exclude_none=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")
        service.save_config(update_dict)
        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update code execution config: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
