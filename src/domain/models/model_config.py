"""
LLM 模型配置数据模型

定义提供商、模型和配置的 Pydantic 模型
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.providers.types import (
    ApiProtocol,
    CallMode,
    EndpointProfile,
    ModelCapabilities,
    ProviderType,
)


class ChatTemplate(BaseModel):
    """Per-model default chat sampling parameters."""

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=1)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)


class Provider(BaseModel):
    """LLM 提供商配置"""

    id: str = Field(..., description="提供商唯一标识")
    name: str = Field(..., description="提供商显示名称")
    type: ProviderType = Field(default=ProviderType.BUILTIN, description="提供商来源类型")
    protocol: ApiProtocol = Field(default=ApiProtocol.OPENAI, description="API 协议类型")
    call_mode: CallMode = Field(default=CallMode.AUTO, description="调用模式")
    base_url: str = Field(..., description="API 基础 URL")
    endpoint_profile_id: str | None = Field(default=None, description="endpoint 配置 ID")
    api_keys: list[str] = Field(default_factory=list, description="多 Key 轮询列表")
    enabled: bool = Field(default=True, description="是否启用")

    # Capability declaration (provider-level defaults)
    default_capabilities: ModelCapabilities | None = Field(
        default=None, description="默认模型能力（provider级别）"
    )

    # Advanced configuration
    url_suffix: str = Field(default="/v1", description="URL 后缀")
    auto_append_path: bool = Field(default=True, description="是否自动拼接路径")
    supports_model_list: bool = Field(default=False, description="是否支持获取模型列表")
    sdk_class: str | None = Field(default=None, description="SDK 适配器类覆盖")
    endpoint_profiles: list[EndpointProfile] = Field(
        default_factory=list, description="可选 endpoint 配置"
    )

    # Runtime fields (not persisted)
    has_api_key: bool | None = Field(default=None, description="是否已配置 API 密钥")
    requires_api_key: bool | None = Field(default=None, description="是否需要 API 密钥")
    api_key: str | None = Field(
        default=None, description="API 密钥（仅用于传输，不持久化到配置文件）"
    )
    source_plugin_id: str | None = Field(default=None, description="来源 provider 插件 ID")
    source_plugin_name: str | None = Field(default=None, description="来源 provider 插件名称")
    source_plugin_version: str | None = Field(default=None, description="来源 provider 插件版本")


class Model(BaseModel):
    """LLM 模型配置"""

    id: str = Field(..., description="模型唯一标识（模型ID）")
    name: str = Field(..., description="模型显示名称")
    provider_id: str = Field(..., description="所属提供商ID")
    tags: list[str] = Field(default_factory=list, description="模型标签")
    enabled: bool = Field(default=True, description="是否启用")

    # Model capabilities (overrides provider defaults)
    capabilities: ModelCapabilities | None = Field(
        default=None, description="模型能力（覆盖 provider 默认值）"
    )
    chat_template: ChatTemplate | None = Field(default=None, description="模型直聊默认参数模板")

    @model_validator(mode="before")
    @classmethod
    def _normalize_tags(cls, data):
        """向后兼容 group 字段，并规范化 tags。"""
        if not isinstance(data, dict):
            return data

        raw_tags = data.get("tags")
        if raw_tags is None:
            raw_tags = data.get("group")

        if isinstance(raw_tags, str):
            candidates = [part.strip() for part in raw_tags.split(",")]
        elif isinstance(raw_tags, list):
            candidates = [str(part).strip() for part in raw_tags]
        elif raw_tags is None:
            candidates = []
        else:
            candidates = [str(raw_tags).strip()]

        normalized: list[str] = []
        seen = set()
        for tag in candidates:
            clean_tag = tag.lower()
            if not clean_tag or clean_tag in seen:
                continue
            normalized.append(clean_tag)
            seen.add(clean_tag)

        data["tags"] = normalized
        data.pop("group", None)
        return data


class DefaultConfig(BaseModel):
    """默认配置"""

    provider: str = Field(..., description="默认提供商ID")
    model: str = Field(..., description="默认模型ID")


class ModelsConfig(BaseModel):
    """完整的模型配置"""

    default: DefaultConfig
    providers: list[Provider]
    models: list[Model]
    reasoning_supported_patterns: list[str] = Field(
        default=[], description="支持 reasoning effort 参数的模型名称模式列表"
    )


class ProviderConfigFile(BaseModel):
    """Persisted provider definitions and local provider overrides."""

    providers: list[Provider] = Field(default_factory=list)


class ModelCatalogFile(BaseModel):
    """Persisted model catalog entries."""

    models: list[Model] = Field(default_factory=list)


class AppDefaultsConfig(BaseModel):
    """Persisted application defaults related to model/provider selection."""

    default: DefaultConfig
    reasoning_supported_patterns: list[str] = Field(
        default_factory=list,
        description="Supported reasoning pattern hints exposed by the app",
    )


class ProviderCreate(BaseModel):
    """创建提供商请求"""

    id: str = Field(..., description="提供商唯一标识")
    name: str = Field(..., description="提供商显示名称")
    type: ProviderType = Field(default=ProviderType.CUSTOM, description="提供商类型")
    protocol: ApiProtocol = Field(default=ApiProtocol.OPENAI, description="API 协议类型")
    call_mode: CallMode = Field(default=CallMode.AUTO, description="调用模式")
    base_url: str = Field(..., description="API 基础 URL")
    endpoint_profile_id: str | None = Field(default=None, description="endpoint 配置 ID")
    api_key: str = Field(default="", description="API 密钥")
    enabled: bool = Field(default=True, description="是否启用")
    default_capabilities: ModelCapabilities | None = Field(default=None, description="默认模型能力")
    auto_append_path: bool = Field(default=True, description="是否自动拼接路径")


class ProviderUpdate(BaseModel):
    """更新提供商请求"""

    name: str | None = Field(default=None, description="提供商显示名称")
    protocol: ApiProtocol | None = Field(default=None, description="API 协议类型")
    call_mode: CallMode | None = Field(default=None, description="调用模式")
    base_url: str | None = Field(default=None, description="API 基础 URL")
    endpoint_profile_id: str | None = Field(default=None, description="endpoint 配置 ID")
    enabled: bool | None = Field(default=None, description="是否启用")
    api_key: str | None = Field(
        None, min_length=1, description="API 密钥（可选，不提供则保持不变）"
    )
    default_capabilities: ModelCapabilities | None = Field(default=None, description="默认模型能力")
    auto_append_path: bool | None = Field(default=None, description="是否自动拼接路径")


class ProviderApiKeyUpdate(BaseModel):
    """更新 API 密钥请求"""

    api_key: str = Field(..., min_length=1, description="API 密钥")


class ProviderTestRequest(BaseModel):
    """测试提供商连接请求"""

    base_url: str = Field(..., description="API 基础 URL")
    api_key: str = Field(default="", description="API 密钥")
    model_id: str | None = Field(default=None, description="用于测试的模型ID")
    provider_id: str | None = Field(
        default=None, description="提供商ID（用于选择正确适配器和默认模型）"
    )


class ProviderTestStoredRequest(BaseModel):
    """使用已存储的API Key测试提供商连接请求"""

    provider_id: str = Field(..., description="提供商ID")
    base_url: str = Field(..., description="API 基础 URL")
    model_id: str | None = Field(default=None, description="用于测试的模型ID")


class ProviderTestResponse(BaseModel):
    """测试提供商连接响应"""

    success: bool = Field(..., description="测试是否成功")
    message: str = Field(..., description="测试结果消息")


class ProviderEndpointProbeRequest(BaseModel):
    """Endpoint 探测请求（自动或手动）。"""

    mode: Literal["auto", "manual"] = Field(default="auto", description="探测模式")
    endpoint_profile_id: str | None = Field(default=None, description="手动模式下指定的 profile ID")
    base_url_override: str | None = Field(default=None, description="手动模式下指定 base URL")
    use_stored_key: bool = Field(default=True, description="是否使用已保存的 API key")
    api_key: str | None = Field(
        default=None, description="显式传入 API key（use_stored_key=false 时）"
    )
    model_id: str | None = Field(default=None, description="可选模型ID（预留）")
    strict: bool = Field(default=True, description="是否启用严格判定（仅真实 API 成功算通过）")
    client_region_hint: Literal["cn", "global", "unknown"] = Field(
        default="unknown",
        description="客户端区域提示，用于推荐排序",
    )


class ProviderEndpointProbeResult(BaseModel):
    """单个 endpoint 的探测结果。"""

    endpoint_profile_id: str | None = Field(default=None, description="endpoint profile ID")
    label: str = Field(..., description="显示名称")
    base_url: str = Field(..., description="被探测的 base URL")
    success: bool = Field(..., description="是否探测成功")
    classification: str = Field(..., description="结果分类")
    http_status: int | None = Field(default=None, description="HTTP 状态码")
    latency_ms: int | None = Field(default=None, description="耗时毫秒")
    message: str = Field(..., description="结果消息")
    detected_model_count: int | None = Field(default=None, description="识别到的模型数")
    priority: int = Field(default=100, description="推荐排序优先级（越小越优先）")
    region_tags: list[str] = Field(default_factory=list, description="endpoint 区域标签")


class ProviderEndpointProbeResponse(BaseModel):
    """Endpoint 探测响应。"""

    provider_id: str = Field(..., description="provider ID")
    results: list[ProviderEndpointProbeResult] = Field(
        default_factory=list, description="探测结果列表"
    )
    recommended_endpoint_profile_id: str | None = Field(default=None, description="推荐 profile ID")
    recommended_base_url: str | None = Field(default=None, description="推荐 base URL")
    summary: str = Field(..., description="结果摘要")


class ProviderEndpointProfilesResponse(BaseModel):
    """Provider endpoint profiles 响应。"""

    provider_id: str = Field(..., description="provider ID")
    current_endpoint_profile_id: str | None = Field(default=None, description="当前 profile ID")
    current_base_url: str = Field(..., description="当前 base URL")
    endpoint_profiles: list[EndpointProfile] = Field(
        default_factory=list, description="endpoint 配置列表"
    )
    recommended_endpoint_profile_id: str | None = Field(
        default=None, description="按区域推荐的 profile ID"
    )


class ModelTestRequest(BaseModel):
    """测试模型连接请求"""

    model_id: str = Field(..., description="模型ID（复合格式 provider_id:model_id）")
