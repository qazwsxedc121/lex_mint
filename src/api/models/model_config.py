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
