"""
模型管理 API 端点

提供商和模型配置的 CRUD 操作
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, List, Optional

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
    ProviderEndpointProbeRequest,
    ProviderEndpointProbeResponse,
    ProviderEndpointProfilesResponse,
    ModelTestRequest,
)
from ..services.model_config_service import ModelConfigService
from ..services.provider_probe_service import ProviderProbeService
from src.providers import (
    BUILTIN_PROVIDERS,
    ModelCapabilities,
    EndpointProfile,
    get_builtin_provider,
)
from src.providers.model_capability_rules import apply_model_capability_hints
from src.providers.types import ApiProtocol, ProviderType

router = APIRouter(prefix="/api/models", tags=["models"])


def get_model_service() -> ModelConfigService:
    """依赖注入：获取模型配置服务实例"""
    return ModelConfigService()


# ==================== 提供商管理 ====================

# NOTE: Static routes must be defined BEFORE parameterized routes
# Otherwise /providers/builtin would match /providers/{provider_id}

class BuiltinProviderInfo(BaseModel):
    """内置 Provider 信息响应"""
    id: str
    name: str
    protocol: str
    base_url: str
    sdk_class: str
    supports_model_list: bool
    default_capabilities: ModelCapabilities
    endpoint_profiles: List[EndpointProfile] = Field(default_factory=list)
    default_endpoint_profile_id: Optional[str] = None


class ModelInfo(BaseModel):
    """模型信息（含可选的能力和标签）"""
    id: str
    name: str
    capabilities: Optional[dict] = None
    tags: Optional[List[str]] = None


@router.get("/providers/builtin", response_model=List[BuiltinProviderInfo])
async def get_builtin_providers():
    """
    获取所有内置 Provider 定义

    Returns pre-configured provider definitions with default settings and models.
    """
    result = []
    for provider_id, definition in BUILTIN_PROVIDERS.items():
        result.append(BuiltinProviderInfo(
            id=definition.id,
            name=definition.name,
            protocol=definition.protocol.value,
            base_url=definition.base_url,
            sdk_class=definition.sdk_class,
            supports_model_list=definition.supports_model_list,
            default_capabilities=definition.default_capabilities,
            endpoint_profiles=definition.endpoint_profiles,
            default_endpoint_profile_id=definition.default_endpoint_profile_id,
        ))
    return result


@router.get("/providers/builtin/{provider_id}", response_model=BuiltinProviderInfo)
async def get_builtin_provider_info(provider_id: str):
    """
    获取指定内置 Provider 的定义

    Args:
        provider_id: Provider ID (e.g., "deepseek", "openai", "openrouter")
    """
    definition = get_builtin_provider(provider_id)
    if not definition:
        raise HTTPException(
            status_code=404,
            detail=f"Builtin provider '{provider_id}' not found"
        )

    return BuiltinProviderInfo(
        id=definition.id,
        name=definition.name,
        protocol=definition.protocol.value,
        base_url=definition.base_url,
        sdk_class=definition.sdk_class,
        supports_model_list=definition.supports_model_list,
        default_capabilities=definition.default_capabilities,
        endpoint_profiles=definition.endpoint_profiles,
        default_endpoint_profile_id=definition.default_endpoint_profile_id,
    )


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
        if provider_data.type == ProviderType.BUILTIN:
            raise HTTPException(
                status_code=400,
                detail="Built-in providers are preloaded. Use create provider for custom providers only."
            )

        # 创建 Provider 对象（不包含 api_key）
        provider = Provider(
            id=provider_data.id,
            name=provider_data.name,
            type=provider_data.type,
            protocol=provider_data.protocol,
            call_mode=provider_data.call_mode,
            base_url=provider_data.base_url,
            endpoint_profile_id=provider_data.endpoint_profile_id,
            enabled=provider_data.enabled,
            default_capabilities=provider_data.default_capabilities,
            auto_append_path=provider_data.auto_append_path,
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
        if provider_update.protocol is not None:
            updated_data['protocol'] = provider_update.protocol
        if provider_update.call_mode is not None:
            updated_data['call_mode'] = provider_update.call_mode
        if provider_update.base_url is not None:
            updated_data['base_url'] = provider_update.base_url
            resolved_profile_id = service.resolve_endpoint_profile_id_for_base_url(
                existing,
                provider_update.base_url,
            )
            updated_data['endpoint_profile_id'] = resolved_profile_id or "custom"
        if provider_update.endpoint_profile_id is not None:
            resolved_base_url = None
            if provider_update.endpoint_profile_id and provider_update.endpoint_profile_id != "custom":
                resolved_base_url = service.resolve_endpoint_profile_base_url(
                    existing,
                    provider_update.endpoint_profile_id,
                )
                if not resolved_base_url:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unknown endpoint profile '{provider_update.endpoint_profile_id}' for provider '{provider_id}'",
                    )
            updated_data['endpoint_profile_id'] = provider_update.endpoint_profile_id
            if resolved_base_url:
                updated_data['base_url'] = resolved_base_url
        if provider_update.enabled is not None:
            updated_data['enabled'] = provider_update.enabled
        if provider_update.default_capabilities is not None:
            updated_data['default_capabilities'] = provider_update.default_capabilities
        if provider_update.auto_append_path is not None:
            updated_data['auto_append_path'] = provider_update.auto_append_path

        # 创建更新后的 Provider 对象（不包含api_key，因为它不在Provider的配置中）
        updated_data.pop('api_key', None)
        updated_data.pop('has_api_key', None)
        updated_data.pop('requires_api_key', None)
        updated_provider = Provider(**updated_data)
        await service.update_provider(provider_id, updated_provider)

        # 如果提供了新的API密钥，则更新
        if provider_update.api_key is not None:
            await service.set_api_key(provider_id, provider_update.api_key)

        return {"message": "Provider updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/providers/{provider_id}/endpoint-profiles",
    response_model=ProviderEndpointProfilesResponse,
)
async def get_provider_endpoint_profiles(
    provider_id: str,
    client_region_hint: str = "unknown",
    service: ModelConfigService = Depends(get_model_service),
):
    """获取 provider 的 endpoint 配置列表。"""
    provider = await service.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    profiles = service.get_endpoint_profiles_for_provider(provider)
    recommended_profile_id = service.recommend_endpoint_profile_id(
        provider,
        client_region_hint=client_region_hint,
    )

    return ProviderEndpointProfilesResponse(
        provider_id=provider_id,
        current_endpoint_profile_id=provider.endpoint_profile_id,
        current_base_url=provider.base_url,
        endpoint_profiles=profiles,
        recommended_endpoint_profile_id=recommended_profile_id,
    )


@router.post(
    "/providers/{provider_id}/probe-endpoints",
    response_model=ProviderEndpointProbeResponse,
)
async def probe_provider_endpoints(
    provider_id: str,
    probe_request: ProviderEndpointProbeRequest,
    service: ModelConfigService = Depends(get_model_service),
):
    """执行 provider endpoint 诊断（自动或手动）。"""
    provider = await service.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    if not probe_request.strict:
        raise HTTPException(status_code=400, detail="Only strict mode is supported")

    api_key = ""
    if probe_request.use_stored_key:
        api_key = (await service.get_api_key(provider_id)) or ""
    elif probe_request.api_key:
        api_key = probe_request.api_key

    if service.provider_requires_api_key(provider) and not api_key:
        raise HTTPException(status_code=400, detail="No API key available for endpoint probing")

    probe_service = ProviderProbeService(service)
    try:
        return await probe_service.probe(
            provider,
            request=probe_request,
            api_key=api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    provider = None
    if test_request.provider_id:
        provider = await service.get_provider(test_request.provider_id)

    success, message = await service.test_provider_connection(
        base_url=test_request.base_url,
        api_key=test_request.api_key,
        model_id=test_request.model_id,
        provider=provider,
    )
    return ProviderTestResponse(success=success, message=message)


@router.post("/providers/test-stored", response_model=ProviderTestResponse)
async def test_provider_stored_connection(
    test_request: ProviderTestStoredRequest,
    service: ModelConfigService = Depends(get_model_service)
):
    """测试提供商连接是否有效（使用已存储的API Key）"""
    # 获取提供商配置
    provider = await service.get_provider(test_request.provider_id)
    if not provider:
        return ProviderTestResponse(
            success=False,
            message=f"Provider '{test_request.provider_id}' not found"
        )

    # 获取已存储的API Key
    api_key = await service.get_api_key(test_request.provider_id)
    if not api_key and service.provider_requires_api_key(provider):
        return ProviderTestResponse(
            success=False,
            message="No API key found for this provider"
        )

    success, message = await service.test_provider_connection(
        base_url=test_request.base_url,
        api_key=api_key or "",
        model_id=test_request.model_id,
        provider=provider
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


@router.get("/list/{model_id:path}", response_model=Model)
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


@router.put("/list/{model_id:path}")
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
        detail = str(e)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail)


@router.delete("/list/{model_id:path}")
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


@router.post("/test-connection", response_model=ProviderTestResponse)
async def test_model_connection(
    test_request: ModelTestRequest,
    service: ModelConfigService = Depends(get_model_service)
):
    """
    测试模型连接是否有效

    自动查找模型配置，使用已存储的 API Key 进行测试
    """
    model_id = test_request.model_id

    # Parse composite model ID (provider_id:model_id)
    if ':' not in model_id:
        return ProviderTestResponse(
            success=False,
            message="Invalid model_id format. Expected format: provider_id:model_id"
        )

    provider_id, simple_model_id = model_id.split(':', 1)

    # Get provider configuration
    provider = await service.get_provider(provider_id)
    if not provider:
        return ProviderTestResponse(
            success=False,
            message=f"Provider '{provider_id}' not found"
        )

    # Get model configuration
    models = await service.get_models(provider_id)
    model = next((m for m in models if m.id == simple_model_id), None)
    if not model:
        return ProviderTestResponse(
            success=False,
            message=f"Model '{simple_model_id}' not found in provider '{provider_id}'"
        )

    # Get API key
    api_key = await service.get_api_key(provider_id)
    if not api_key:
        return ProviderTestResponse(
            success=False,
            message=f"No API key configured for provider '{provider_id}'"
        )

    # Test connection
    success, message = await service.test_provider_connection(
        base_url=provider.base_url,
        api_key=api_key,
        model_id=simple_model_id,
        provider=provider
    )

    return ProviderTestResponse(success=success, message=message)


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


# ==================== Reasoning 配置 ====================

@router.get("/reasoning-patterns", response_model=List[str])
async def get_reasoning_supported_patterns(
    service: ModelConfigService = Depends(get_model_service)
):
    """获取支持 reasoning effort 参数的模型名称模式列表"""
    return await service.get_reasoning_supported_patterns()


# ==================== Provider 抽象层 API (其他端点) ====================

class CapabilitiesResponse(BaseModel):
    """模型能力响应"""
    model_id: str
    provider_id: str
    capabilities: ModelCapabilities


@router.post("/providers/{provider_id}/fetch-models", response_model=List[ModelInfo])
async def fetch_provider_models(
    provider_id: str,
    service: ModelConfigService = Depends(get_model_service)
):
    """
    从 Provider API 获取可用模型列表

    Calls the provider's /models endpoint to get available models.
    Only works for providers that support model listing.

    Args:
        provider_id: Provider ID
    """
    # Get provider config
    provider = await service.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    # Check if provider supports model listing
    builtin = get_builtin_provider(provider_id)
    supports_list = (
        builtin.supports_model_list if builtin
        else getattr(provider, 'supports_model_list', False)
    )

    if not supports_list:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider_id}' does not support model listing"
        )

    # Get API key (optional - some providers like OpenRouter have public model lists)
    api_key = await service.get_api_key(provider_id) or ""

    # Get adapter and fetch models
    adapter = service.get_adapter_for_provider(provider)
    try:
        models = await adapter.fetch_models(provider.base_url, api_key)
        if not models and not api_key:
            raise HTTPException(
                status_code=400,
                detail=f"No models found. Try configuring an API key for provider '{provider_id}'"
            )
        model_infos: List[ModelInfo] = []
        for m in models:
            raw_capabilities: Any = m.get("capabilities")
            capabilities = raw_capabilities if isinstance(raw_capabilities, dict) else None
            capabilities = apply_model_capability_hints(
                m["id"],
                capabilities,
                provider_id=provider_id,
            )

            raw_tags: Any = m.get("tags")
            tags: Optional[List[str]]
            if isinstance(raw_tags, list):
                tags = [str(tag) for tag in raw_tags]
            elif isinstance(raw_tags, str):
                tags = [part.strip() for part in raw_tags.split(",") if part.strip()]
            else:
                tags = None

            model_infos.append(
                ModelInfo(
                    id=m["id"],
                    name=m.get("name", m["id"]),
                    capabilities=capabilities,
                    tags=tags,
                )
            )
        return model_infos
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch models: {str(e)}"
        )


@router.get("/capabilities/{model_id:path}", response_model=CapabilitiesResponse)
async def get_model_capabilities(
    model_id: str,
    service: ModelConfigService = Depends(get_model_service)
):
    """
    获取模型的能力配置

    Returns merged capabilities (provider defaults + model overrides).

    Args:
        model_id: Model ID (can be composite: provider_id:model_id)
                  Supports model IDs with slashes (e.g., openrouter:bytedance-seed/seed-1.6-flash)
    """
    model = await service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    provider = await service.get_provider(model.provider_id)
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{model.provider_id}' not found"
        )

    capabilities = service.get_merged_capabilities(model, provider)

    return CapabilitiesResponse(
        model_id=model.id,
        provider_id=model.provider_id,
        capabilities=capabilities,
    )


@router.get("/protocols", response_model=List[dict])
async def get_available_protocols():
    """
    获取可用的 API 协议类型

    Returns list of supported API protocols for custom providers.
    """
    return [
        {"id": ApiProtocol.OPENAI.value, "name": "OpenAI Compatible", "description": "OpenAI and compatible APIs"},
        {"id": ApiProtocol.ANTHROPIC.value, "name": "Anthropic", "description": "Anthropic Claude API"},
        {"id": ApiProtocol.GEMINI.value, "name": "Google Gemini", "description": "Google Gemini API"},
        {"id": ApiProtocol.OLLAMA.value, "name": "Ollama", "description": "Ollama local models"},
    ]
