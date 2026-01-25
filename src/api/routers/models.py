"""
模型管理 API 端点

提供商和模型配置的 CRUD 操作
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional

from ..models.model_config import Provider, Model, DefaultConfig
from ..services.model_config_service import ModelConfigService

router = APIRouter(prefix="/api/models", tags=["models"])


def get_model_service() -> ModelConfigService:
    """依赖注入：获取模型配置服务实例"""
    return ModelConfigService()


# ==================== 提供商管理 ====================

@router.get("/providers", response_model=List[Provider])
async def list_providers(service: ModelConfigService = Depends(get_model_service)):
    """获取所有提供商列表"""
    return await service.get_providers()


@router.get("/providers/{provider_id}", response_model=Provider)
async def get_provider(
    provider_id: str,
    service: ModelConfigService = Depends(get_model_service)
):
    """获取指定提供商详情"""
    provider = await service.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    return provider


@router.post("/providers", status_code=201)
async def create_provider(
    provider: Provider,
    service: ModelConfigService = Depends(get_model_service)
):
    """创建新提供商"""
    try:
        await service.add_provider(provider)
        return {"message": "Provider created successfully", "id": provider.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: str,
    provider: Provider,
    service: ModelConfigService = Depends(get_model_service)
):
    """更新提供商信息"""
    try:
        await service.update_provider(provider_id, provider)
        return {"message": "Provider updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: str,
    service: ModelConfigService = Depends(get_model_service)
):
    """删除提供商（级联删除关联模型）"""
    try:
        await service.delete_provider(provider_id)
        return {"message": "Provider deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 模型管理 ====================

@router.get("/list", response_model=List[Model])
async def list_models(
    provider_id: Optional[str] = None,
    service: ModelConfigService = Depends(get_model_service)
):
    """
    获取模型列表

    Args:
        provider_id: 可选，按提供商筛选
    """
    return await service.get_models(provider_id)


@router.get("/list/{model_id}", response_model=Model)
async def get_model(
    model_id: str,
    service: ModelConfigService = Depends(get_model_service)
):
    """获取指定模型详情"""
    model = await service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return model


@router.post("/list", status_code=201)
async def create_model(
    model: Model,
    service: ModelConfigService = Depends(get_model_service)
):
    """创建新模型"""
    try:
        await service.add_model(model)
        return {"message": "Model created successfully", "id": model.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/list/{model_id}")
async def update_model(
    model_id: str,
    model: Model,
    service: ModelConfigService = Depends(get_model_service)
):
    """更新模型信息"""
    try:
        await service.update_model(model_id, model)
        return {"message": "Model updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/list/{model_id}")
async def delete_model(
    model_id: str,
    service: ModelConfigService = Depends(get_model_service)
):
    """删除模型"""
    try:
        await service.delete_model(model_id)
        return {"message": "Model deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 默认配置 ====================

@router.get("/default", response_model=DefaultConfig)
async def get_default_config(service: ModelConfigService = Depends(get_model_service)):
    """获取默认模型配置"""
    return await service.get_default_config()


@router.put("/default")
async def set_default_config(
    provider_id: str,
    model_id: str,
    service: ModelConfigService = Depends(get_model_service)
):
    """设置默认模型"""
    try:
        await service.set_default_model(provider_id, model_id)
        return {"message": "Default model updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
