"""Tool gate config API router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.routers.service_protocols import ConfigSaveServiceLike
from src.infrastructure.config.tool_gate_config_service import ToolGateConfigService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tool-gate", tags=["tool-gate"])


class ToolGateRuleResponse(BaseModel):
    id: str
    enabled: bool
    priority: int
    pattern: str
    flags: str
    include_tools: list[str]
    exclude_tools: list[str]
    description: str | None = None


class ToolGateConfigResponse(BaseModel):
    enabled: bool
    rules: list[ToolGateRuleResponse]


class ToolGateRuleUpdate(BaseModel):
    id: str = Field(..., min_length=1, max_length=120)
    enabled: bool = True
    priority: int = Field(default=0, ge=-100000, le=100000)
    pattern: str = Field(..., min_length=1, max_length=1000)
    flags: str = Field(default="", max_length=8)
    include_tools: list[str] = Field(default_factory=list, max_length=64)
    exclude_tools: list[str] = Field(default_factory=list, max_length=64)
    description: str | None = Field(default=None, max_length=500)


class ToolGateConfigUpdate(BaseModel):
    enabled: bool | None = None
    rules: list[ToolGateRuleUpdate] | None = None


def get_tool_gate_config_service() -> ToolGateConfigService:
    return ToolGateConfigService()


@router.get("/config", response_model=ToolGateConfigResponse)
async def get_config(service: ConfigSaveServiceLike = Depends(get_tool_gate_config_service)):
    """Get current tool-gate config."""
    try:
        cfg = service.config
        return ToolGateConfigResponse(
            enabled=bool(getattr(cfg, "enabled", False)),
            rules=[
                ToolGateRuleResponse(
                    id=str(rule.id),
                    enabled=bool(rule.enabled),
                    priority=int(rule.priority),
                    pattern=str(rule.pattern),
                    flags=str(rule.flags),
                    include_tools=list(rule.include_tools),
                    exclude_tools=list(rule.exclude_tools),
                    description=rule.description,
                )
                for rule in list(getattr(cfg, "rules", []) or [])
            ],
        )
    except Exception as exc:
        logger.error("Failed to get tool gate config: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/config")
async def update_config(
    updates: ToolGateConfigUpdate,
    service: ConfigSaveServiceLike = Depends(get_tool_gate_config_service),
):
    """Update tool-gate config."""
    try:
        update_dict = updates.model_dump(exclude_none=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")
        service.save_config(update_dict)
        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to update tool gate config: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
