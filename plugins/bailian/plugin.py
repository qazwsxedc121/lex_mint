"""Alibaba Cloud Bailian provider plugin entrypoint."""

from src.providers.plugins.models import ProviderPluginContribution
from src.providers.types import ApiProtocol, ModelCapabilities, ProviderDefinition

from .adapter import BailianAdapter


def register_provider() -> ProviderPluginContribution:
    return ProviderPluginContribution(
        adapters={"bailian": BailianAdapter},
        builtin_providers=[
            ProviderDefinition(
                id="bailian",
                name="Alibaba Cloud (Qwen)",
                protocol=ApiProtocol.OPENAI,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                sdk_class="bailian",
                default_capabilities=ModelCapabilities(
                    context_length=131072,
                    vision=False,
                    function_calling=True,
                    reasoning=True,
                    streaming=True,
                    file_upload=False,
                    image_output=False,
                ),
                url_suffix="",
                auto_append_path=False,
                supports_model_list=True,
                endpoint_profiles=[],
                default_endpoint_profile_id=None,
            )
        ],
    )
