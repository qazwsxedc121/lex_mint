"""
Prompt template management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
import uuid

from ..models.prompt_template import (
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
)
from ..services.prompt_template_service import PromptTemplateConfigService

router = APIRouter(prefix="/api/prompt-templates", tags=["prompt-templates"])


def get_prompt_template_service() -> PromptTemplateConfigService:
    return PromptTemplateConfigService()


@router.get("", response_model=List[PromptTemplate])
async def list_prompt_templates(service: PromptTemplateConfigService = Depends(get_prompt_template_service)):
    return await service.get_templates()


@router.get("/{template_id}", response_model=PromptTemplate)
async def get_prompt_template(
    template_id: str,
    service: PromptTemplateConfigService = Depends(get_prompt_template_service)
):
    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return template


@router.post("", status_code=201)
async def create_prompt_template(
    template_data: PromptTemplateCreate,
    service: PromptTemplateConfigService = Depends(get_prompt_template_service)
):
    try:
        template_id = template_data.id or str(uuid.uuid4())
        template_payload = template_data.model_dump()
        template_payload["id"] = template_id
        template = PromptTemplate(**template_payload)
        await service.add_template(template)
        return {"message": "Template created successfully", "id": template_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{template_id}")
async def update_prompt_template(
    template_id: str,
    template_update: PromptTemplateUpdate,
    service: PromptTemplateConfigService = Depends(get_prompt_template_service)
):
    try:
        existing = await service.get_template(template_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

        updated_data = existing.model_dump()
        for field, value in template_update.model_dump(exclude_unset=True).items():
            if value is not None:
                updated_data[field] = value

        updated_template = PromptTemplate(**updated_data)
        await service.update_template(template_id, updated_template)
        return {"message": "Template updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{template_id}")
async def delete_prompt_template(
    template_id: str,
    service: PromptTemplateConfigService = Depends(get_prompt_template_service)
):
    try:
        await service.delete_template(template_id)
        return {"message": "Template deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
