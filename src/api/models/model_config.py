"""
LLM 模型配置数据模型

定义提供商、模型和配置的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from pydantic import model_validator
from typing import List, Optional

from src.providers.types import ApiProtocol, ProviderType, ModelCapabilities


class Provider(BaseModel):
    """LLM 提供商配置"""
    id: str = Field(..., description="提供商唯一标识")
    name: str = Field(..., description="提供商显示名称")
    type: ProviderType = Field(default=ProviderType.BUILTIN, description="提供商来源类型")
    protocol: ApiProtocol = Field(default=ApiProtocol.OPENAI, description="API 协议类型")
    base_url: str = Field(..., description="API 基础 URL")
    api_keys: List[str] = Field(default_factory=list, description="多 Key 轮询列表")
    enabled: bool = Field(default=True, description="是否启用")

    # Capability declaration (provider-level defaults)
    default_capabilities: Optional[ModelCapabilities] = Field(
        default=None,
        description="默认模型能力（provider级别）"
    )

    # Advanced configuration
    url_suffix: str = Field(default="/v1", description="URL 后缀")
    auto_append_path: bool = Field(default=True, description="是否自动拼接路径")
    supports_model_list: bool = Field(default=False, description="是否支持获取模型列表")
    sdk_class: Optional[str] = Field(default=None, description="SDK 适配器类覆盖")

    # Runtime fields (not persisted)
    has_api_key: Optional[bool] = Field(default=None, description="是否已配置 API 密钥")
    api_key: Optional[str] = Field(default=None, description="API 密钥（仅用于传输，不持久化到配置文件）")


class Model(BaseModel):
    """LLM 模型配置"""
    id: str = Field(..., description="模型唯一标识（模型ID）")
    name: str = Field(..., description="模型显示名称")
    provider_id: str = Field(..., description="所属提供商ID")
    tags: List[str] = Field(default_factory=list, description="模型标签")
    enabled: bool = Field(default=True, description="是否启用")

    # Model capabilities (overrides provider defaults)
    capabilities: Optional[ModelCapabilities] = Field(
        default=None,
        description="模型能力（覆盖 provider 默认值）"
    )

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

        normalized: List[str] = []
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
    providers: List[Provider]
    models: List[Model]
    reasoning_supported_patterns: List[str] = Field(
        default=[],
        description="支持 reasoning effort 参数的模型名称模式列表"
    )


class ProviderCreate(BaseModel):
    """创建提供商请求"""
    id: str = Field(..., description="提供商唯一标识")
    name: str = Field(..., description="提供商显示名称")
    type: ProviderType = Field(default=ProviderType.CUSTOM, description="提供商类型")
    protocol: ApiProtocol = Field(default=ApiProtocol.OPENAI, description="API 协议类型")
    base_url: str = Field(..., description="API 基础 URL")
    api_key: str = Field(default="", description="API 密钥")
    enabled: bool = Field(default=True, description="是否启用")
    default_capabilities: Optional[ModelCapabilities] = Field(default=None, description="默认模型能力")
    auto_append_path: bool = Field(default=True, description="是否自动拼接路径")


class ProviderUpdate(BaseModel):
    """更新提供商请求"""
    name: Optional[str] = Field(None, description="提供商显示名称")
    protocol: Optional[ApiProtocol] = Field(None, description="API 协议类型")
    base_url: Optional[str] = Field(None, description="API 基础 URL")
    enabled: Optional[bool] = Field(None, description="是否启用")
    api_key: Optional[str] = Field(None, min_length=1, description="API 密钥（可选，不提供则保持不变）")
    default_capabilities: Optional[ModelCapabilities] = Field(None, description="默认模型能力")
    auto_append_path: Optional[bool] = Field(None, description="是否自动拼接路径")


class ProviderApiKeyUpdate(BaseModel):
    """更新 API 密钥请求"""
    api_key: str = Field(..., min_length=1, description="API 密钥")


class ProviderTestRequest(BaseModel):
    """测试提供商连接请求"""
    base_url: str = Field(..., description="API 基础 URL")
    api_key: str = Field(..., min_length=1, description="API 密钥")
    model_id: str = Field(default="gpt-3.5-turbo", description="用于测试的模型ID")


class ProviderTestStoredRequest(BaseModel):
    """使用已存储的API Key测试提供商连接请求"""
    provider_id: str = Field(..., description="提供商ID")
    base_url: str = Field(..., description="API 基础 URL")
    model_id: str = Field(default="gpt-3.5-turbo", description="用于测试的模型ID")


class ProviderTestResponse(BaseModel):
    """测试提供商连接响应"""
    success: bool = Field(..., description="测试是否成功")
    message: str = Field(..., description="测试结果消息")


class ModelTestRequest(BaseModel):
    """测试模型连接请求"""
    model_id: str = Field(..., description="模型ID（复合格式 provider_id:model_id）")
