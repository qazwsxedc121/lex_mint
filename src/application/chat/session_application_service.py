"""Application-facing session operations for chat and group chat."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, cast

from src.application.chat.chat_runtime.settings import GroupSettingsResolver
from src.domain.models.group_participant import parse_group_participant


ALLOWED_OVERRIDE_KEYS = {
    "model_id",
    "temperature",
    "max_tokens",
    "top_p",
    "top_k",
    "frequency_penalty",
    "presence_penalty",
    "max_rounds",
}

PARAM_RANGES = {
    "temperature": (0, 2),
    "max_tokens": (1, 8192),
    "top_p": (0, 1),
    "top_k": (1, 200),
    "frequency_penalty": (-2, 2),
    "presence_penalty": (-2, 2),
    "max_rounds": (-1, 1000),
}


@dataclass(frozen=True)
class SessionApplicationDeps:
    """Dependencies required by SessionApplicationService."""

    storage: Any
    assistant_service: Any
    model_service: Any
    file_service: Any


class SessionApplicationService:
    """Owns session-level application commands used by API routes."""

    def __init__(self, deps: SessionApplicationDeps):
        self._storage = deps.storage
        self._assistant_service = deps.assistant_service
        self._model_service = deps.model_service
        self._file_service = deps.file_service

    @staticmethod
    def normalize_target_type(
        target_type: Optional[str],
        *,
        assistant_id: Optional[str],
        model_id: Optional[str],
    ) -> Optional[str]:
        if target_type is not None:
            normalized = target_type.strip().lower()
            if normalized not in {"assistant", "model"}:
                raise ValueError("target_type must be one of: assistant, model")
            return normalized

        if assistant_id:
            return "assistant"
        if model_id:
            return "model"
        return None

    async def normalize_and_validate_group_assistants(
        self,
        group_assistants: Optional[List[str]],
    ) -> Optional[List[str]]:
        if group_assistants is None:
            return None

        normalized: List[str] = []
        seen = set()
        for participant_token in group_assistants:
            if not isinstance(participant_token, str):
                raise ValueError("group participant IDs must be strings")
            participant = parse_group_participant(participant_token)
            stable_token = participant.token
            if stable_token in seen:
                continue
            seen.add(stable_token)
            normalized.append(stable_token)

        if len(normalized) < 2:
            raise ValueError("Group chat requires at least 2 unique participants")

        for participant_token in normalized:
            participant = parse_group_participant(participant_token)
            if participant.kind == "assistant":
                await self._assistant_service.require_enabled_assistant(participant.value)
                continue
            await self._model_service.require_enabled_model(participant.value)

        return normalized

    @staticmethod
    def normalize_and_validate_group_mode(
        group_mode: Optional[str],
        group_assistants: Optional[List[str]],
    ) -> Optional[str]:
        normalized_mode = GroupSettingsResolver.normalize_group_mode(
            group_mode,
            group_assistants=group_assistants,
        )
        if group_mode is not None and normalized_mode is None:
            raise ValueError("group_mode must be one of: round_robin, committee")
        if group_mode is not None and not group_assistants:
            raise ValueError("group_mode requires group_assistants")
        return normalized_mode

    @staticmethod
    def normalize_group_settings_payload(
        group_settings: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if group_settings is None:
            return None
        if not isinstance(group_settings, dict):
            raise ValueError("group_settings must be an object")
        return GroupSettingsResolver.normalize_group_settings(group_settings)

    @staticmethod
    def _deep_merge_dict(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = SessionApplicationService._deep_merge_dict(merged[key], value)
            else:
                merged[key] = value
        return merged

    async def _load_assistant_config_map(self, group_assistants: List[str]) -> Dict[str, Any]:
        assistant_config_map: Dict[str, Any] = {}
        for assistant_id in group_assistants:
            assistant_obj = await self._assistant_service.get_assistant(assistant_id)
            if assistant_obj:
                assistant_config_map[assistant_id] = assistant_obj
        return assistant_config_map

    def _copy_session_attachments(self, source_session_id: str, target_session_id: str) -> None:
        source_dir = Path(self._file_service.attachments_dir) / source_session_id
        if not source_dir.exists():
            return

        target_dir = Path(self._file_service.attachments_dir) / target_session_id
        target_dir.mkdir(parents=True, exist_ok=True)

        for entry in source_dir.iterdir():
            if entry.name == "temp":
                continue
            destination = target_dir / entry.name
            if entry.is_dir():
                shutil.copytree(entry, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(entry, destination)

    async def create_session(
        self,
        *,
        assistant_id: Optional[str],
        model_id: Optional[str],
        target_type: Optional[str],
        temporary: bool,
        group_assistants: Optional[List[str]],
        group_mode: Optional[str],
        group_settings: Optional[Dict[str, Any]],
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> str:
        normalized_target_type = self.normalize_target_type(
            target_type,
            assistant_id=assistant_id,
            model_id=model_id,
        )
        normalized_group_assistants = await self.normalize_and_validate_group_assistants(group_assistants)
        normalized_group_mode = self.normalize_and_validate_group_mode(
            group_mode,
            normalized_group_assistants,
        )
        normalized_group_settings = self.normalize_group_settings_payload(group_settings)
        if normalized_group_settings is not None and not normalized_group_assistants:
            raise ValueError("group_settings requires group_assistants")

        return cast(
            str,
            await self._storage.create_session(
            model_id=model_id,
            assistant_id=assistant_id,
            target_type=normalized_target_type,
            context_type=context_type,
            project_id=project_id,
            temporary=temporary,
            group_assistants=normalized_group_assistants,
            group_mode=normalized_group_mode,
            group_settings=normalized_group_settings,
            ),
        )

    async def delete_session(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        await self._storage.delete_session(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def save_temporary_session(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        await self._storage.convert_to_permanent(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def update_session_target(
        self,
        *,
        session_id: str,
        target_type: Literal["assistant", "model"],
        assistant_id: Optional[str] = None,
        model_id: Optional[str] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        await self._storage.update_session_target(
            session_id,
            target_type=target_type,
            assistant_id=assistant_id,
            model_id=model_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def update_group_assistants(
        self,
        *,
        session_id: str,
        group_assistants: List[str],
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        normalized = await self.normalize_and_validate_group_assistants(group_assistants)
        if normalized is None:
            raise ValueError("group_assistants is required")
        await self._storage.update_group_assistants(
            session_id,
            normalized,
            context_type=context_type,
            project_id=project_id,
        )

    async def get_group_settings(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        session = await self._storage.get_session(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )
        group_assistants = session.get("group_assistants") or []
        if len(group_assistants) < 2:
            raise ValueError("Session is not a group chat")

        group_mode = self.normalize_and_validate_group_mode(
            session.get("group_mode"),
            group_assistants,
        ) or "round_robin"
        raw_group_settings = GroupSettingsResolver.normalize_group_settings(
            session.get("group_settings") if isinstance(session.get("group_settings"), dict) else None
        )
        assistant_config_map = await self._load_assistant_config_map(group_assistants)
        resolved = GroupSettingsResolver.resolve(
            group_mode=group_mode,
            group_assistants=group_assistants,
            group_settings=raw_group_settings,
            assistant_config_map=assistant_config_map,
        )
        return {
            "group_mode": group_mode,
            "group_assistants": group_assistants,
            "group_settings": raw_group_settings,
            "effective_settings": resolved.to_effective_dict(),
        }

    async def update_group_settings(
        self,
        *,
        session_id: str,
        group_assistants: Optional[List[str]] = None,
        group_mode: Optional[str] = None,
        group_settings: Optional[Dict[str, Any]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        session = await self._storage.get_session(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )
        existing_group_assistants = session.get("group_assistants")
        if group_assistants is not None:
            next_group_assistants = await self.normalize_and_validate_group_assistants(group_assistants)
        else:
            next_group_assistants = existing_group_assistants

        if not next_group_assistants or len(next_group_assistants) < 2:
            raise ValueError("Group chat requires at least 2 unique assistants")

        next_group_mode = self.normalize_and_validate_group_mode(
            group_mode if group_mode is not None else session.get("group_mode"),
            next_group_assistants,
        ) or "round_robin"

        existing_group_settings = GroupSettingsResolver.normalize_group_settings(
            session.get("group_settings") if isinstance(session.get("group_settings"), dict) else None
        )
        if group_settings is not None:
            update_settings = self.normalize_group_settings_payload(group_settings) or {"version": 1}
            next_group_settings = self._deep_merge_dict(existing_group_settings, update_settings)
        else:
            next_group_settings = existing_group_settings

        assistant_config_map = await self._load_assistant_config_map(next_group_assistants)
        resolved = GroupSettingsResolver.resolve(
            group_mode=next_group_mode,
            group_assistants=next_group_assistants,
            group_settings=next_group_settings,
            assistant_config_map=assistant_config_map,
        )

        await self._storage.update_session_metadata(
            session_id=session_id,
            metadata_updates={
                "group_assistants": next_group_assistants,
                "group_mode": next_group_mode,
                "group_settings": next_group_settings,
            },
            context_type=context_type,
            project_id=project_id,
        )
        return {
            "message": "Group settings updated",
            "group_mode": next_group_mode,
            "group_assistants": next_group_assistants,
            "group_settings": next_group_settings,
            "effective_settings": resolved.to_effective_dict(),
        }

    async def update_session_title(
        self,
        *,
        session_id: str,
        title: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        await self._storage.update_session_metadata(
            session_id,
            {"title": title},
            context_type=context_type,
            project_id=project_id,
        )

    async def update_param_overrides(
        self,
        *,
        session_id: str,
        overrides: Dict[str, Any],
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        invalid_keys = set(overrides.keys()) - ALLOWED_OVERRIDE_KEYS
        if invalid_keys:
            raise ValueError(f"Invalid override keys: {invalid_keys}")

        for key, value in overrides.items():
            if key == "model_id":
                if not isinstance(value, str) or ":" not in value:
                    raise ValueError("model_id must be in 'provider:model' format")
                await self._model_service.require_enabled_model(value)
                continue

            if key in PARAM_RANGES:
                if not isinstance(value, (int, float)):
                    raise ValueError(f"{key} must be a number")
                min_val, max_val = PARAM_RANGES[key]
                if value < min_val or value > max_val:
                    raise ValueError(f"{key} must be between {min_val} and {max_val}")

        await self._storage.update_session_metadata(
            session_id,
            {"param_overrides": overrides},
            context_type=context_type,
            project_id=project_id,
        )

    async def branch_session(
        self,
        *,
        session_id: str,
        message_id: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> str:
        original_session = await self._storage.get_session(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )
        original_messages = original_session.get("state", {}).get("messages", [])
        branch_index = None
        for index, message in enumerate(original_messages):
            if message.get("message_id") == message_id:
                branch_index = index
                break
        if branch_index is None:
            raise ValueError(f"message_id '{message_id}' not found in session")

        truncated_messages = original_messages[:branch_index + 1]
        assistant_id = original_session.get("assistant_id")
        model_id = original_session.get("model_id")
        new_session_id = await self._storage.create_session(
            model_id=model_id,
            assistant_id=assistant_id,
            context_type=context_type,
            project_id=project_id,
        )
        original_title = original_session.get("title", "New Chat")
        await self._storage.update_session_metadata(
            new_session_id,
            {"title": f"{original_title} (Branch)"},
            context_type=context_type,
            project_id=project_id,
        )
        if truncated_messages:
            await self._storage.set_messages(
                new_session_id,
                truncated_messages,
                context_type=context_type,
                project_id=project_id,
            )
        return cast(str, new_session_id)

    async def duplicate_session(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> str:
        original_session = await self._storage.get_session(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )
        assistant_id = original_session.get("assistant_id")
        model_id = original_session.get("model_id")
        new_session_id = await self._storage.create_session(
            model_id=model_id,
            assistant_id=assistant_id,
            context_type=context_type,
            project_id=project_id,
        )
        original_title = original_session.get("title", "New Chat")
        await self._storage.update_session_metadata(
            new_session_id,
            {"title": f"{original_title} (Copy)"},
            context_type=context_type,
            project_id=project_id,
        )
        original_messages = original_session.get("state", {}).get("messages", [])
        if original_messages:
            await self._storage.set_messages(
                new_session_id,
                original_messages,
                context_type=context_type,
                project_id=project_id,
            )
        return cast(str, new_session_id)

    async def move_session(
        self,
        *,
        session_id: str,
        source_context_type: str = "chat",
        source_project_id: Optional[str] = None,
        target_context_type: str = "chat",
        target_project_id: Optional[str] = None,
    ) -> None:
        await self._storage.move_session(
            session_id,
            source_context_type=source_context_type,
            source_project_id=source_project_id,
            target_context_type=target_context_type,
            target_project_id=target_project_id,
        )

    async def copy_session(
        self,
        *,
        session_id: str,
        source_context_type: str = "chat",
        source_project_id: Optional[str] = None,
        target_context_type: str = "chat",
        target_project_id: Optional[str] = None,
    ) -> str:
        new_session_id = await self._storage.copy_session(
            session_id,
            source_context_type=source_context_type,
            source_project_id=source_project_id,
            target_context_type=target_context_type,
            target_project_id=target_project_id,
        )
        self._copy_session_attachments(session_id, new_session_id)
        return cast(str, new_session_id)

    async def update_session_folder(
        self,
        *,
        session_id: str,
        folder_id: Optional[str],
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        await self._storage.update_session_folder(
            session_id=session_id,
            folder_id=folder_id,
            context_type=context_type,
            project_id=project_id,
        )
