"""
模型配置管理服务

负责加载、保存和管理 LLM 提供商和模型配置
"""
import os
import yaml
import aiofiles
from pathlib import Path
from typing import List, Optional
from langchain_openai import ChatOpenAI

from ..models.model_config import Provider, Model, DefaultConfig, ModelsConfig


class ModelConfigService:
    """模型配置管理服务"""

    def __init__(self, config_path: Path = None, keys_path: Path = None):
        """
        初始化配置服务

        Args:
            config_path: 配置文件路径，默认为项目根目录的 models_config.yaml
            keys_path: 密钥文件路径，默认为项目根目录的 keys_config.yaml
        """
        if config_path is None:
            # 默认配置文件在项目根目录
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "models_config.yaml"
        if keys_path is None:
            # 默认密钥文件在项目根目录
            keys_path = Path(__file__).parent.parent.parent.parent / "config" / "keys_config.yaml"
        self.config_path = config_path
        self.keys_path = keys_path
        self._ensure_config_exists()
        self._ensure_keys_config_exists()

    def _ensure_config_exists(self):
        """确保配置文件存在，如果不存在则创建默认配置"""
        if not self.config_path.exists():
            default_config = self._get_default_config()
            # 同步写入初始配置
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(default_config, f, allow_unicode=True, sort_keys=False)

    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            "default": {
                "provider": "deepseek",
                "model": "deepseek-chat"
            },
            "providers": [
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "base_url": "https://api.deepseek.com",
                    "api_key_env": "DEEPSEEK_API_KEY",
                    "enabled": True
                },
                {
                    "id": "openai",
                    "name": "OpenAI",
                    "base_url": "https://api.openai.com/v1",
                    "api_key_env": "OPENAI_API_KEY",
                    "enabled": False
                }
            ],
            "models": [
                {
                    "id": "deepseek-chat",
                    "name": "DeepSeek Chat",
                    "provider_id": "deepseek",
                    "group": "对话模型",
                    "temperature": 0.7,
                    "enabled": True
                },
                {
                    "id": "deepseek-coder",
                    "name": "DeepSeek Coder",
                    "provider_id": "deepseek",
                    "group": "代码模型",
                    "temperature": 0.7,
                    "enabled": True
                },
                {
                    "id": "gpt-4-turbo",
                    "name": "GPT-4 Turbo",
                    "provider_id": "openai",
                    "group": "对话模型",
                    "temperature": 0.7,
                    "enabled": False
                },
                {
                    "id": "gpt-3.5-turbo",
                    "name": "GPT-3.5 Turbo",
                    "provider_id": "openai",
                    "group": "对话模型",
                    "temperature": 0.7,
                    "enabled": False
                }
            ]
        }

    async def load_config(self) -> ModelsConfig:
        """加载配置文件"""
        async with aiofiles.open(self.config_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = yaml.safe_load(content)
            return ModelsConfig(**data)

    async def save_config(self, config: ModelsConfig):
        """
        保存配置文件（原子性写入）

        使用临时文件 + 替换的方式确保原子性
        """
        # 先写入临时文件
        temp_path = self.config_path.with_suffix('.yaml.tmp')
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            content = yaml.safe_dump(
                config.model_dump(),
                allow_unicode=True,
                sort_keys=False
            )
            await f.write(content)

        # 原子性替换
        temp_path.replace(self.config_path)

    def _ensure_keys_config_exists(self):
        """确保密钥配置文件存在，如果不存在则创建空配置"""
        if not self.keys_path.exists():
            default_keys = {"providers": {}}
            with open(self.keys_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(default_keys, f, allow_unicode=True, sort_keys=False)

    async def load_keys_config(self) -> dict:
        """加载密钥配置文件"""
        async with aiofiles.open(self.keys_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = yaml.safe_load(content)
            return data if data else {"providers": {}}

    async def save_keys_config(self, keys_data: dict):
        """
        保存密钥配置文件（原子性写入）

        使用临时文件 + 替换的方式确保原子性
        """
        # 先写入临时文件
        temp_path = self.keys_path.with_suffix('.yaml.tmp')
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            content = yaml.safe_dump(
                keys_data,
                allow_unicode=True,
                sort_keys=False
            )
            await f.write(content)

        # 原子性替换
        temp_path.replace(self.keys_path)

    async def get_api_key(self, provider_id: str) -> Optional[str]:
        """
        获取指定提供商的 API 密钥

        Args:
            provider_id: 提供商ID

        Returns:
            API 密钥，如果不存在则返回 None
        """
        keys_data = await self.load_keys_config()
        return keys_data.get("providers", {}).get(provider_id, {}).get("api_key")

    async def set_api_key(self, provider_id: str, api_key: str):
        """
        设置/更新指定提供商的 API 密钥

        Args:
            provider_id: 提供商ID
            api_key: API 密钥
        """
        keys_data = await self.load_keys_config()
        if "providers" not in keys_data:
            keys_data["providers"] = {}
        if provider_id not in keys_data["providers"]:
            keys_data["providers"][provider_id] = {}
        keys_data["providers"][provider_id]["api_key"] = api_key
        await self.save_keys_config(keys_data)

    async def delete_api_key(self, provider_id: str):
        """
        删除指定提供商的 API 密钥

        Args:
            provider_id: 提供商ID
        """
        keys_data = await self.load_keys_config()
        if "providers" in keys_data and provider_id in keys_data["providers"]:
            del keys_data["providers"][provider_id]
            await self.save_keys_config(keys_data)

    async def has_api_key(self, provider_id: str) -> bool:
        """
        检查指定提供商是否已配置 API 密钥

        Args:
            provider_id: 提供商ID

        Returns:
            如果已配置密钥返回 True，否则返回 False
        """
        api_key = await self.get_api_key(provider_id)
        return api_key is not None and api_key.strip() != ""

    # ==================== 提供商管理 ====================

    async def get_providers(self) -> List[Provider]:
        """获取所有提供商（包含 has_api_key 标记）"""
        config = await self.load_config()
        providers_with_keys = []
        for provider in config.providers:
            # 检查是否有 API 密钥
            has_key = await self.has_api_key(provider.id)
            # 创建新的 Provider 对象，添加 has_api_key 字段
            provider_dict = provider.model_dump()
            provider_dict['has_api_key'] = has_key
            providers_with_keys.append(Provider(**provider_dict))
        return providers_with_keys

    async def get_provider(self, provider_id: str, include_masked_key: bool = False) -> Optional[Provider]:
        """
        获取指定提供商

        Args:
            provider_id: 提供商ID
            include_masked_key: 是否包含遮罩后的API密钥（用于编辑界面显示）
        """
        config = await self.load_config()
        for provider in config.providers:
            if provider.id == provider_id:
                provider_dict = provider.model_dump()

                # 添加 has_api_key 标记
                has_key = await self.has_api_key(provider_id)
                provider_dict['has_api_key'] = has_key

                # 如果需要，添加遮罩后的API密钥
                if include_masked_key and has_key:
                    api_key = await self.get_api_key(provider_id)
                    if api_key:
                        provider_dict['api_key'] = self._mask_api_key(api_key)

                return Provider(**provider_dict)
        return None

    def _mask_api_key(self, api_key: str) -> str:
        """
        遮罩API密钥，只显示前缀和后4位

        例如: sk-ba6c70ee741c45beb53f89da4280087c -> sk-****...087c
        """
        if len(api_key) <= 8:
            return "****"
        return f"{api_key[:3]}****...{api_key[-4:]}"

    async def add_provider(self, provider: Provider):
        """
        添加提供商

        Raises:
            ValueError: 如果提供商ID已存在
        """
        config = await self.load_config()

        # 检查ID是否已存在
        if any(p.id == provider.id for p in config.providers):
            raise ValueError(f"Provider with id '{provider.id}' already exists")

        # 移除临时字段，避免保存到配置文件
        provider_dict = provider.model_dump(exclude={'api_key', 'has_api_key'})
        config.providers.append(Provider(**provider_dict))
        await self.save_config(config)

    async def update_provider(self, provider_id: str, updated: Provider):
        """
        更新提供商

        Raises:
            ValueError: 如果提供商不存在
        """
        config = await self.load_config()

        for i, provider in enumerate(config.providers):
            if provider.id == provider_id:
                # 移除临时字段，避免保存到配置文件
                updated_dict = updated.model_dump(exclude={'api_key', 'has_api_key'})
                config.providers[i] = Provider(**updated_dict)
                await self.save_config(config)
                return

        raise ValueError(f"Provider with id '{provider_id}' not found")

    async def delete_provider(self, provider_id: str):
        """
        删除提供商（级联删除关联的模型）

        Raises:
            ValueError: 如果提供商不存在或是默认提供商
        """
        config = await self.load_config()

        # 检查是否是默认提供商
        if config.default.provider == provider_id:
            raise ValueError(f"Cannot delete default provider '{provider_id}'")

        # 删除提供商
        config.providers = [p for p in config.providers if p.id != provider_id]

        # 级联删除关联的模型
        config.models = [m for m in config.models if m.provider_id != provider_id]

        await self.save_config(config)

    # ==================== 模型管理 ====================

    async def get_models(self, provider_id: Optional[str] = None) -> List[Model]:
        """
        获取模型列表

        Args:
            provider_id: 可选的提供商ID，用于筛选
        """
        config = await self.load_config()
        if provider_id:
            return [m for m in config.models if m.provider_id == provider_id]
        return config.models

    async def get_model(self, model_id: str) -> Optional[Model]:
        """
        获取指定模型

        Args:
            model_id: 模型ID，可以是简单ID或复合ID (provider_id:model_id)
        """
        config = await self.load_config()

        # 支持复合ID格式 "provider_id:model_id"
        if ':' in model_id:
            provider_id, simple_model_id = model_id.split(':', 1)
            for model in config.models:
                if model.id == simple_model_id and model.provider_id == provider_id:
                    return model
        else:
            # 简单ID：直接匹配（向后兼容）
            for model in config.models:
                if model.id == model_id:
                    return model

        return None

    async def add_model(self, model: Model):
        """
        添加模型

        Raises:
            ValueError: 如果模型在该提供商下已存在，或提供商不存在
        """
        config = await self.load_config()

        # 检查同一个提供商下是否有重复的模型ID（复合主键）
        if any(m.id == model.id and m.provider_id == model.provider_id
               for m in config.models):
            raise ValueError(
                f"Model '{model.id}' already exists for provider '{model.provider_id}'"
            )

        # 检查提供商是否存在
        if not any(p.id == model.provider_id for p in config.providers):
            raise ValueError(f"Provider with id '{model.provider_id}' not found")

        config.models.append(model)
        await self.save_config(config)

    async def update_model(self, model_id: str, updated: Model):
        """
        更新模型

        Raises:
            ValueError: 如果模型不存在
        """
        config = await self.load_config()

        for i, model in enumerate(config.models):
            if model.id == model_id:
                config.models[i] = updated
                await self.save_config(config)
                return

        raise ValueError(f"Model with id '{model_id}' not found")

    async def delete_model(self, model_id: str):
        """
        删除模型

        Args:
            model_id: 模型ID，可以是简单ID或复合ID (provider_id:model_id)

        Raises:
            ValueError: 如果模型不存在或是默认模型
        """
        config = await self.load_config()

        # 解析复合ID
        if ':' in model_id:
            provider_id, simple_model_id = model_id.split(':', 1)
            composite_default = f"{config.default.provider}:{config.default.model}"

            # 检查是否是默认模型
            if model_id == composite_default or (
                simple_model_id == config.default.model and
                provider_id == config.default.provider
            ):
                raise ValueError(f"Cannot delete default model '{model_id}'")

            # 删除模型
            original_count = len(config.models)
            config.models = [
                m for m in config.models
                if not (m.id == simple_model_id and m.provider_id == provider_id)
            ]
        else:
            # 简单ID（向后兼容）
            if config.default.model == model_id:
                raise ValueError(f"Cannot delete default model '{model_id}'")

            original_count = len(config.models)
            config.models = [m for m in config.models if m.id != model_id]

        if len(config.models) == original_count:
            raise ValueError(f"Model with id '{model_id}' not found")

        await self.save_config(config)

    # ==================== 默认配置 ====================

    async def get_default_config(self) -> DefaultConfig:
        """获取默认配置"""
        config = await self.load_config()
        return config.default

    async def set_default_model(self, provider_id: str, model_id: str):
        """
        设置默认模型

        Raises:
            ValueError: 如果提供商或模型不存在
        """
        config = await self.load_config()

        # 验证提供商存在
        if not any(p.id == provider_id for p in config.providers):
            raise ValueError(f"Provider with id '{provider_id}' not found")

        # 验证模型存在且属于该提供商
        model = next((m for m in config.models if m.id == model_id), None)
        if not model:
            raise ValueError(f"Model with id '{model_id}' not found")
        if model.provider_id != provider_id:
            raise ValueError(f"Model '{model_id}' does not belong to provider '{provider_id}'")

        config.default.provider = provider_id
        config.default.model = model_id
        await self.save_config(config)

    async def get_reasoning_supported_patterns(self) -> list[str]:
        """获取支持 reasoning effort 参数的模型名称模式列表"""
        config = await self.load_config()
        return config.reasoning_supported_patterns

    # ==================== 测试连接 ====================

    async def test_provider_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: str = "gpt-3.5-turbo"
    ) -> tuple[bool, str]:
        """
        测试提供商连接是否有效

        Args:
            base_url: API基础URL
            api_key: API密钥
            model_id: 用于测试的模型ID（默认使用通用的模型名）

        Returns:
            (是否成功, 消息)
        """
        try:
            # 创建临时 LLM 实例
            test_llm = ChatOpenAI(
                model=model_id,
                temperature=0.0,
                base_url=base_url,
                api_key=api_key,
                timeout=10.0,  # 10秒超时
                max_retries=0  # 不重试
            )

            # 发送简单的测试消息
            from langchain_core.messages import HumanMessage
            response = await test_llm.ainvoke([
                HumanMessage(content="test")
            ])

            if response and response.content:
                return True, "Connection successful"
            else:
                return False, "No response from API"

        except Exception as e:
            error_msg = str(e)
            # 简化错误信息
            if "authentication" in error_msg.lower() or "unauthorized" in error_msg.lower():
                return False, "Authentication failed: Invalid API key"
            elif "not found" in error_msg.lower() or "404" in error_msg:
                return False, "API endpoint not found: Check base URL"
            elif "timeout" in error_msg.lower():
                return False, "Connection timeout: API not responding"
            elif "connection" in error_msg.lower():
                return False, f"Connection error: {error_msg}"
            else:
                return False, f"Test failed: {error_msg}"

    # ==================== LLM 实例化 ====================

    def get_llm_instance(self, model_id: Optional[str] = None) -> ChatOpenAI:
        """
        创建 LLM 实例（同步方法）

        Args:
            model_id: 模型ID，可以是简单ID或复合ID (provider_id:model_id)
                     如果为 None 则使用默认模型

        Returns:
            ChatOpenAI 实例

        Raises:
            ValueError: 如果模型不存在或配置无效
            RuntimeError: 如果 API 密钥环境变量不存在
        """
        # 同步加载配置
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            config = ModelsConfig(**data)

        # 确定使用哪个模型
        if model_id is None:
            # 使用默认模型（复合ID）
            model_id = f"{config.default.provider}:{config.default.model}"

        # 查找模型（支持复合ID）
        model = None
        if ':' in model_id:
            provider_id, simple_model_id = model_id.split(':', 1)
            model = next(
                (m for m in config.models
                 if m.id == simple_model_id and m.provider_id == provider_id),
                None
            )
        else:
            # 简单ID：直接匹配（向后兼容）
            model = next((m for m in config.models if m.id == model_id), None)

        if not model:
            raise ValueError(f"Model with id '{model_id}' not found")

        # 查找提供商
        provider = next((p for p in config.providers if p.id == model.provider_id), None)
        if not provider:
            raise ValueError(f"Provider with id '{model.provider_id}' not found")

        # 获取 API 密钥（先尝试从 YAML 加载，然后回退到环境变量）
        # 同步读取 keys_config.yaml
        api_key = None
        if self.keys_path.exists():
            try:
                with open(self.keys_path, 'r', encoding='utf-8') as f:
                    keys_data = yaml.safe_load(f)
                    if keys_data and "providers" in keys_data:
                        provider_keys = keys_data["providers"].get(provider.id, {})
                        api_key = provider_keys.get("api_key")
            except Exception:
                pass  # 如果读取失败，继续尝试环境变量

        # 回退到环境变量（向后兼容）
        if not api_key:
            api_key = os.getenv(provider.api_key_env)

        if not api_key:
            raise RuntimeError(
                f"API key not found for provider '{provider.id}'. "
                f"Please set it via the UI or environment variable: {provider.api_key_env}"
            )

        # 创建 LLM 实例
        return ChatOpenAI(
            model=model.id,
            temperature=model.temperature,
            base_url=provider.base_url,
            api_key=api_key
        )
