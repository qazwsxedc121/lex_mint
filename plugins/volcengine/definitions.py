"""VolcEngine provider plugin definitions."""

from src.providers.plugins.models import ProviderPluginContribution
from src.providers.types import ApiProtocol, ModelCapabilities, ProviderDefinition

from .adapter import VolcEngineAdapter


def register_provider() -> ProviderPluginContribution:
    return ProviderPluginContribution(
        adapters={"volcengine": VolcEngineAdapter},
        builtin_providers=[
            ProviderDefinition(
                id="volcengine",
                name="Volcano Engine (Doubao)",
                protocol=ApiProtocol.OPENAI,
                base_url="https://ark.cn-beijing.volces.com/api/v3",
                sdk_class="volcengine",
                default_capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
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
