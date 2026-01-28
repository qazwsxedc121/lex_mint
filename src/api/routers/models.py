"""
模型管理 API 端点

提供商和模型配置的 CRUD 操作
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional

from ..models.model_config import (
    Provider,
    Model,
    DefaultConfig,
    ProviderCreate,
    ProviderUpdate,
    ProviderApiKeyUpdate,
    ProviderTestRequest,
    ProviderTestStoredRequest,
    ProviderTestResponse,
)
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
    include_masked_key: bool = False,
    service: ModelConfigService = Depends(get_model_service)
):
    """
    获取指定提供商详情

    Args:
        provider_id: 提供商ID
        include_masked_key: 是否包含遮罩后的API密钥（用于编辑）
    """
    provider = await service.get_provider(provider_id, include_masked_key=include_masked_key)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    return provider


@router.post("/providers", status_code=201)
async def create_provider(
    provider_data: ProviderCreate,
    service: ModelConfigService = Depends(get_model_service)
):
    """创建新提供商（包含 API 密钥）"""
    try:
        # 创建 Provider 对象（不包含 api_key）
        provider = Provider(
            id=provider_data.id,
            name=provider_data.name,
            base_url=provider_data.base_url,
            api_key_env=f"{provider_data.id.upper()}_API_KEY",  # 生成默认环境变量名
            enabled=provider_data.enabled
        )
        # 添加提供商配置
        await service.add_provider(provider)
        # 保存 API 密钥
        await service.set_api_key(provider_data.id, provider_data.api_key)
        return {"message": "Provider created successfully", "id": provider_data.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: str,
    provider_update: ProviderUpdate,
    service: ModelConfigService = Depends(get_model_service)
):
    """
    更新提供商信息（包括可选的API密钥）

    如果 api_key 字段提供了新值，则更新密钥；否则保持原密钥不变
    """
    try:
        # 获取现有提供商
        existing = await service.get_provider(provider_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

        # 合并更新（只更新提供的字段）
        updated_data = existing.model_dump()
        if provider_update.name is not None:
            updated_data['name'] = provider_update.name
        if provider_update.base_url is not None:
            updated_data['base_url'] = provider_update.base_url
        if provider_update.enabled is not None:
            updated_data['enabled'] = provider_update.enabled

        # 创建更新后的 Provider 对象（不包含api_key，因为它不在Provider的配置中）
        updated_data.pop('api_key', None)
        updated_data.pop('has_api_key', None)
        updated_provider = Provider(**updated_data)
        await service.update_provider(provider_id, updated_provider)

        # 如果提供了新的API密钥，则更新
        if provider_update.api_key is not None:
            await service.set_api_key(provider_id, provider_update.api_key)

        return {"message": "Provider updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: str,
    service: ModelConfigService = Depends(get_model_service)
):
    """删除提供商（级联删除关联模型和 API 密钥）"""
    try:
        await service.delete_provider(provider_id)
        # 同时删除 API 密钥
        await service.delete_api_key(provider_id)
        return {"message": "Provider deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/providers/test", response_model=ProviderTestResponse)
async def test_provider_connection(
    test_request: ProviderTestRequest,
    service: ModelConfigService = Depends(get_model_service)
):
    """测试提供商连接是否有效（使用提供的API Key）"""
    success, message = await service.test_provider_connection(
        base_url=test_request.base_url,
        api_key=test_request.api_key,
        model_id=test_request.model_id
    )
    return ProviderTestResponse(success=success, message=message)


@router.post("/providers/test-stored", response_model=ProviderTestResponse)
async def test_provider_stored_connection(
    test_request: ProviderTestStoredRequest,
    service: ModelConfigService = Depends(get_model_service)
):
    """测试提供商连接是否有效（使用已存储的API Key）"""
    # 获取已存储的API Key
    api_key = await service.get_api_key(test_request.provider_id)
    if not api_key:
        return ProviderTestResponse(
            success=False,
            message="No API key found for this provider"
        )

    success, message = await service.test_provider_connection(
        base_url=test_request.base_url,
        api_key=api_key,
        model_id=test_request.model_id
    )
    return ProviderTestResponse(success=success, message=message)


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
