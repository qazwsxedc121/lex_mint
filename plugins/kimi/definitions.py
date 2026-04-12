"""Kimi provider plugin definitions."""

from src.providers.plugins.models import ProviderPluginContribution
from src.providers.types import ApiProtocol, ModelCapabilities, ProviderDefinition

from .adapter import KimiAdapter


def register_provider() -> ProviderPluginContribution:
    return ProviderPluginContribution(
        adapters={"kimi": KimiAdapter},
        builtin_providers=[
            ProviderDefinition(
                id="kimi",
                name="Moonshot (Kimi)",
                protocol=ApiProtocol.OPENAI,
                base_url="https://api.moonshot.cn/v1",
                sdk_class="kimi",
                default_capabilities=ModelCapabilities(
                    context_length=262144,
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
                endpoint_profiles=[],
                default_endpoint_profile_id=None,
            )
        ],
    )
