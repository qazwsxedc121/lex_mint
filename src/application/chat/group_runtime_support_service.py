"""Application helpers for resolving group-chat runtime participants and settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.api.services.group_participants import parse_group_participant
from src.api.services.orchestration import GroupSettingsResolver
from src.api.services.service_contracts import AssistantLike


@dataclass
class _RuntimeAssistant:
    id: str
    name: str
    model_id: str
    icon: str
    description: str
    system_prompt: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    top_p: Optional[float]
    top_k: Optional[int]
    frequency_penalty: Optional[float]
    presence_penalty: Optional[float]
    max_rounds: Optional[int]
    memory_enabled: bool
    knowledge_base_ids: Optional[List[str]]
    enabled: bool


class GroupRuntimeSupportService:
    """Resolve group participants and settings for runtime orchestration."""

    @staticmethod
    def _extract_model_template_params(model_obj: Any) -> Dict[str, Any]:
        template = getattr(model_obj, "chat_template", None)
        if not template:
            return {}
        if hasattr(template, "model_dump"):
            raw_template = template.model_dump(exclude_none=True)
        elif isinstance(template, dict):
            raw_template = {key: value for key, value in template.items() if value is not None}
        else:
            return {}
        return {
            "temperature": raw_template.get("temperature"),
            "max_tokens": raw_template.get("max_tokens"),
            "top_p": raw_template.get("top_p"),
            "top_k": raw_template.get("top_k"),
            "frequency_penalty": raw_template.get("frequency_penalty"),
            "presence_penalty": raw_template.get("presence_penalty"),
        }

    async def build_group_runtime_assistant(
        self,
        participant_token: str,
    ) -> Optional[Tuple[str, AssistantLike, str]]:
        """Resolve assistant/model participant token to runtime assistant object."""
        try:
            participant = parse_group_participant(participant_token)
        except ValueError:
            return None

        if participant.kind == "assistant":
            from src.api.services.assistant_config_service import AssistantConfigService

            assistant_service = AssistantConfigService()
            try:
                assistant_obj = await assistant_service.require_enabled_assistant(participant.value)
            except ValueError:
                return None
            return participant.token, assistant_obj, assistant_obj.name

        from src.infrastructure.config.model_config_service import ModelConfigService

        model_service = ModelConfigService()
        try:
            model_obj, _provider_obj = await model_service.require_enabled_model(participant.value)
        except ValueError:
            return None

        composite_model_id = f"{model_obj.provider_id}:{model_obj.id}"
        template_params = self._extract_model_template_params(model_obj)
        runtime_assistant = _RuntimeAssistant(
            id=participant.token,
            name=model_obj.name or model_obj.id,
            icon="CpuChip",
            description=f"Direct model participant: {composite_model_id}",
            model_id=composite_model_id,
            system_prompt=None,
            temperature=template_params.get("temperature", 0.7),
            max_tokens=template_params.get("max_tokens"),
            top_p=template_params.get("top_p"),
            top_k=template_params.get("top_k"),
            frequency_penalty=template_params.get("frequency_penalty"),
            presence_penalty=template_params.get("presence_penalty"),
            max_rounds=None,
            memory_enabled=False,
            knowledge_base_ids=[],
            enabled=True,
        )
        return participant.token, runtime_assistant, runtime_assistant.name

    def resolve_group_settings(
        self,
        *,
        group_mode: Optional[str],
        group_assistants: List[str],
        group_settings: Optional[Dict[str, Any]],
        assistant_config_map: Dict[str, AssistantLike],
        resolve_round_policy: Optional[Callable[..., Dict[str, int]]] = None,
    ) -> Any:
        """Resolve runtime group settings with backward-compatible defaults."""
        return GroupSettingsResolver.resolve(
            group_mode=group_mode,
            group_assistants=group_assistants,
            group_settings=group_settings,
            assistant_config_map=assistant_config_map,
            resolve_round_policy=resolve_round_policy,
        )
