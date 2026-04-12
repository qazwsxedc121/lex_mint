"""StepFun provider plugin definitions."""

from src.providers.plugins.models import ProviderPluginContribution
from src.providers.types import ApiProtocol, EndpointProfile, ModelCapabilities, ProviderDefinition


def register_provider() -> ProviderPluginContribution:
    return ProviderPluginContribution(
        builtin_providers=[
            ProviderDefinition(
                id="stepfun",
                name="StepFun",
                protocol=ApiProtocol.OPENAI,
                base_url="https://api.stepfun.com/v1",
                sdk_class="openai",
                default_capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=False,
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
                        id="stepfun-cn",
                        label="China Mainland (.com)",
                        base_url="https://api.stepfun.com/v1",
                        region_tags=["cn"],
                        priority=10,
                        probe_method="openai_models",
                    ),
                    EndpointProfile(
                        id="stepfun-global",
                        label="Global (.ai)",
                        base_url="https://api.stepfun.ai/v1",
                        region_tags=["global"],
                        priority=20,
                        probe_method="openai_models",
                    ),
                ],
                default_endpoint_profile_id="stepfun-cn",
            )
        ]
    )
