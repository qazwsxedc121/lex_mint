"""Target-resolution helpers for conversation session metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import frontmatter


@dataclass(frozen=True)
class ResolvedSessionTarget:
    """Resolved session target metadata."""

    target_type: str
    assistant_id: Optional[str]
    model_id: str
    param_overrides: dict[str, Any]


class ConversationSessionTargetResolver:
    """Resolve assistant/model session targets without embedding storage logic."""

    def __init__(self, assistant_service: object | None = None, model_service: object | None = None):
        self.assistant_service = assistant_service
        self.model_service = model_service

    async def resolve_target(
        self,
        *,
        target_type: Optional[str],
        assistant_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> ResolvedSessionTarget:
        normalized_target_type = (target_type or "").strip().lower() if target_type else None
        if normalized_target_type not in {None, "assistant", "model"}:
            raise ValueError("target_type must be one of: assistant, model")

        if assistant_id and str(assistant_id).startswith("__legacy_model_"):
            assistant_id = None

        if normalized_target_type is None:
            if assistant_id:
                normalized_target_type = "assistant"
            elif model_id:
                normalized_target_type = "model"

        if normalized_target_type == "assistant":
            assistant_service = self._get_assistant_service()
            if assistant_id:
                assistant = await assistant_service.require_enabled_assistant(assistant_id)
            else:
                assistant = await assistant_service.get_default_assistant()
                assistant_id = assistant.id
            return ResolvedSessionTarget(
                target_type="assistant",
                assistant_id=assistant_id,
                model_id=assistant.model_id,
                param_overrides={},
            )

        if normalized_target_type == "model":
            model_service = self._get_model_service()
            if model_id:
                model_obj, _provider_obj = await model_service.require_enabled_model(model_id)
            else:
                model_obj, _provider_obj = await model_service.require_enabled_model()
            return ResolvedSessionTarget(
                target_type="model",
                assistant_id=None,
                model_id=f"{model_obj.provider_id}:{model_obj.id}",
                param_overrides=self.extract_model_chat_template_overrides(model_obj),
            )

        assistant_service = self._get_assistant_service()
        default_assistant = await assistant_service.get_default_assistant()
        return ResolvedSessionTarget(
            target_type="assistant",
            assistant_id=default_assistant.id,
            model_id=default_assistant.model_id,
            param_overrides={},
        )

    async def apply_target_metadata(
        self,
        post: frontmatter.Post,
        *,
        target_type: str,
        assistant_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> None:
        resolved = await self.resolve_target(
            target_type=target_type,
            assistant_id=assistant_id,
            model_id=model_id,
        )
        if resolved.target_type == "assistant":
            post.metadata["assistant_id"] = resolved.assistant_id
        else:
            post.metadata.pop("assistant_id", None)
        post.metadata["model_id"] = resolved.model_id
        post.metadata["target_type"] = resolved.target_type
        post.metadata["param_overrides"] = resolved.param_overrides

    @staticmethod
    def extract_model_chat_template_overrides(model_obj: Any) -> dict[str, Any]:
        template = getattr(model_obj, "chat_template", None)
        if not template:
            return {}
        if hasattr(template, "model_dump"):
            raw_template = template.model_dump(exclude_none=True)
        elif isinstance(template, dict):
            raw_template = {k: v for k, v in template.items() if v is not None}
        else:
            return {}
        if not isinstance(raw_template, dict):
            return {}

        allowed_keys = {
            "temperature",
            "max_tokens",
            "top_p",
            "top_k",
            "frequency_penalty",
            "presence_penalty",
        }
        return {k: raw_template[k] for k in allowed_keys if k in raw_template}

    def _get_assistant_service(self) -> Any:
        if self.assistant_service is None:
            from src.infrastructure.config.assistant_config_service import AssistantConfigService

            self.assistant_service = AssistantConfigService()
        return self.assistant_service

    def _get_model_service(self) -> Any:
        if self.model_service is None:
            from src.api.services.model_config_service import ModelConfigService

            self.model_service = ModelConfigService()
        return self.model_service
