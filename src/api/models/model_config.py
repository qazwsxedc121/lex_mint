"""
LLM 模型配置数据模型

定义提供商、模型和配置的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class Provider(BaseModel):
    """LLM 提供商配置"""
    id: str = Field(..., description="提供商唯一标识")
    name: str = Field(..., description="提供商显示名称")
    base_url: str = Field(..., description="API 基础 URL")
    api_key_env: str = Field(..., description="API 密钥环境变量名")
    enabled: bool = Field(default=True, description="是否启用")
    has_api_key: Optional[bool] = Field(default=None, description="是否已配置 API 密钥")
    api_key: Optional[str] = Field(default=None, description="API 密钥（仅用于传输，不持久化到配置文件）")


class Model(BaseModel):
    """LLM 模型配置"""
    id: str = Field(..., description="模型唯一标识（模型ID）")
    name: str = Field(..., description="模型显示名称")
    provider_id: str = Field(..., description="所属提供商ID")
    group: str = Field(default="通用", description="模型分组名称")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    enabled: bool = Field(default=True, description="是否启用")


class DefaultConfig(BaseModel):
    """默认配置"""
    provider: str = Field(..., description="默认提供商ID")
    model: str = Field(..., description="默认模型ID")


class ModelsConfig(BaseModel):
    """完整的模型配置"""
    default: DefaultConfig
    providers: List[Provider]
    models: List[Model]


class ProviderCreate(BaseModel):
    """创建提供商请求"""
    id: str = Field(..., description="提供商唯一标识")
    name: str = Field(..., description="提供商显示名称")
    base_url: str = Field(..., description="API 基础 URL")
    api_key: str = Field(..., min_length=1, description="API 密钥")
    enabled: bool = Field(default=True, description="是否启用")


class ProviderUpdate(BaseModel):
    """更新提供商请求"""
    name: Optional[str] = Field(None, description="提供商显示名称")
    base_url: Optional[str] = Field(None, description="API 基础 URL")
    enabled: Optional[bool] = Field(None, description="是否启用")
    api_key: Optional[str] = Field(None, min_length=1, description="API 密钥（可选，不提供则保持不变）")


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
