"""MiniMax provider plugin definitions."""

from src.providers.plugins.models import ProviderPluginContribution
from src.providers.types import ApiProtocol, ModelCapabilities, ProviderDefinition


def register_provider() -> ProviderPluginContribution:
    return ProviderPluginContribution(
        builtin_providers=[
            ProviderDefinition(
                id="minimax",
                name="MiniMax",
                protocol=ApiProtocol.OPENAI,
                base_url="https://api.minimax.chat/v1",
                sdk_class="openai",
                default_capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=False,
                    function_calling=True,
                    reasoning=False,
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
        ]
    )
