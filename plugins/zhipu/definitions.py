"""Zhipu provider plugin definitions."""

from src.providers.plugins.models import ProviderPluginContribution
from src.providers.types import ApiProtocol, EndpointProfile, ModelCapabilities, ProviderDefinition

from .adapter import ZhipuAdapter


def register_provider() -> ProviderPluginContribution:
    return ProviderPluginContribution(
        adapters={"zhipu": ZhipuAdapter},
        builtin_providers=[
            ProviderDefinition(
                id="zhipu",
                name="Zhipu (GLM)",
                protocol=ApiProtocol.OPENAI,
                base_url="https://open.bigmodel.cn/api/paas/v4",
                sdk_class="zhipu",
                default_capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
                    function_calling=True,
                    reasoning=True,
                    streaming=True,
                    file_upload=False,
                    image_output=False,
                ),
                url_suffix="/v1",
                auto_append_path=True,
                supports_model_list=True,
                endpoint_profiles=[
                    EndpointProfile(
                        id="zhipu-cn",
                        label="China Mainland (.cn)",
                        base_url="https://open.bigmodel.cn/api/paas/v4",
                        region_tags=["cn"],
                        priority=10,
                        probe_method="openai_models",
                    )
                ],
                default_endpoint_profile_id="zhipu-cn",
            )
        ],
    )
