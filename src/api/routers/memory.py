"""Memory API router."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.memory_config_service import MemoryConfigService
from ..services.memory_service import MemoryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemorySettingsResponse(BaseModel):
    enabled: bool
    profile_id: str
    collection_name: str
    enabled_layers: List[str]
    top_k: int
    score_threshold: float
    max_injected_items: int
    max_item_length: int
    auto_extract_enabled: bool
    min_text_length: int
    max_items_per_turn: int
    global_enabled: bool
    assistant_enabled: bool


class MemorySettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    profile_id: Optional[str] = None
    collection_name: Optional[str] = None
    enabled_layers: Optional[List[str]] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=30)
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_injected_items: Optional[int] = Field(default=None, ge=1, le=20)
    max_item_length: Optional[int] = Field(default=None, ge=50, le=800)
    auto_extract_enabled: Optional[bool] = None
    min_text_length: Optional[int] = Field(default=None, ge=1, le=200)
    max_items_per_turn: Optional[int] = Field(default=None, ge=1, le=20)
    global_enabled: Optional[bool] = None
    assistant_enabled: Optional[bool] = None


class MemoryCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    scope: Literal["global", "assistant"] = "global"
    layer: str = Field(default="preference")
    assistant_id: Optional[str] = None
    profile_id: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    importance: float = Field(default=0.6, ge=0.0, le=1.0)
    source_session_id: Optional[str] = None
    source_message_id: Optional[str] = None
    pinned: bool = False


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = Field(default=None, min_length=1)
    scope: Optional[Literal["global", "assistant"]] = None
    layer: Optional[str] = None
    assistant_id: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    pinned: Optional[bool] = None
    is_active: Optional[bool] = None


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    profile_id: Optional[str] = None
    assistant_id: Optional[str] = None
    scope: Optional[Literal["global", "assistant"]] = None
    layer: Optional[str] = None
    include_global: bool = True
    include_assistant: bool = True
    limit: int = Field(default=6, ge=1, le=20)


class MemoryListResponse(BaseModel):
    items: List[Dict[str, Any]]
    count: int


def get_memory_config_service() -> MemoryConfigService:
    return MemoryConfigService()


def get_memory_service() -> MemoryService:
    return MemoryService()


@router.get("/settings", response_model=MemorySettingsResponse)
async def get_memory_settings(
    service: MemoryConfigService = Depends(get_memory_config_service),
):
    try:
        return MemorySettingsResponse(**service.get_flat_config())
    except Exception as e:
        logger.error("Failed to load memory settings: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings")
async def update_memory_settings(
    updates: MemorySettingsUpdate,
    service: MemoryConfigService = Depends(get_memory_config_service),
):
    try:
        data = updates.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(status_code=400, detail="No updates provided")

        service.save_flat_config(data)
        return {"message": "Memory settings updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update memory settings: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    profile_id: Optional[str] = None,
    scope: Optional[Literal["global", "assistant"]] = None,
    assistant_id: Optional[str] = None,
    layer: Optional[str] = None,
    include_inactive: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    service: MemoryService = Depends(get_memory_service),
):
    try:
        items = service.list_memories(
            profile_id=profile_id,
            scope=scope,
            assistant_id=assistant_id,
            layer=layer,
            limit=limit,
            include_inactive=include_inactive,
        )
        return MemoryListResponse(items=items, count=len(items))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to list memories: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_memory(
    request: MemoryCreateRequest,
    service: MemoryService = Depends(get_memory_service),
):
    try:
        item = service.upsert_memory(
            content=request.content,
            scope=request.scope,
            layer=request.layer,
            assistant_id=request.assistant_id,
            profile_id=request.profile_id,
            confidence=request.confidence,
            importance=request.importance,
            source_session_id=request.source_session_id,
            source_message_id=request.source_message_id,
            pinned=request.pinned,
        )
        return {"message": "Memory saved", "item": item}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to save memory: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    request: MemoryUpdateRequest,
    service: MemoryService = Depends(get_memory_service),
):
    try:
        updates = request.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        item = service.update_memory(memory_id, **updates)
        return {"message": "Memory updated", "item": item}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update memory: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    service: MemoryService = Depends(get_memory_service),
):
    try:
        service.delete_memory(memory_id)
        return {"message": "Memory deleted", "id": memory_id}
    except Exception as e:
        logger.error("Failed to delete memory: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_memory(
    request: MemorySearchRequest,
    service: MemoryService = Depends(get_memory_service),
):
    try:
        if request.scope:
            items = service.search_memories(
                query=request.query,
                profile_id=request.profile_id,
                scope=request.scope,
                assistant_id=request.assistant_id,
                layer=request.layer,
                top_k=request.limit,
            )
        else:
            items = service.search_memories_for_scopes(
                query=request.query,
                assistant_id=request.assistant_id,
                profile_id=request.profile_id,
                include_global=request.include_global,
                include_assistant=request.include_assistant,
                layer=request.layer,
                limit=request.limit,
            )

        context, _ = service.build_memory_context(
            query=request.query,
            assistant_id=request.assistant_id,
            profile_id=request.profile_id,
            include_global=request.include_global,
            include_assistant=request.include_assistant,
        )
        return {
            "items": items,
            "count": len(items),
            "context": context,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to search memory: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
