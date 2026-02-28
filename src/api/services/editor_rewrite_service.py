"""Inline editor rewrite service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional

from src.agents.simple_llm import call_llm_stream

from ..config import settings
from .assistant_config_service import AssistantConfigService
from .conversation_storage import ConversationStorage, create_storage_with_project_resolver
from .think_tag_filter import ThinkTagStreamFilter


@dataclass
class RewriteRuntimeConfig:
    """Resolved runtime model and generation parameters for one rewrite call."""

    model_id: str
    system_prompt: Optional[str]
    generation_params: Dict[str, Any]


class EditorRewriteService:
    """Streams rewritten text for an in-editor selected region."""

    _PARAM_KEYS = (
        "temperature",
        "max_tokens",
        "top_p",
        "top_k",
        "frequency_penalty",
        "presence_penalty",
    )

    def __init__(self, storage: Optional[ConversationStorage] = None):
        self.storage = storage or create_storage_with_project_resolver(settings.conversations_dir)

    async def stream_rewrite(
        self,
        *,
        session_id: str,
        selected_text: str,
        instruction: Optional[str],
        context_before: str,
        context_after: str,
        file_path: Optional[str],
        language: Optional[str],
        context_type: str = "project",
        project_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream rewritten text chunks while hiding internal think blocks."""

        runtime = await self._resolve_runtime_config(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        )
        system_prompt = self._build_system_prompt(runtime.system_prompt)
        user_prompt = self._build_user_prompt(
            selected_text=selected_text,
            instruction=instruction,
            context_before=context_before,
            context_after=context_after,
            file_path=file_path,
            language=language,
        )

        think_filter = ThinkTagStreamFilter()
        async for chunk in call_llm_stream(
            messages=[{"role": "user", "content": user_prompt}],
            session_id=session_id,
            model_id=runtime.model_id,
            system_prompt=system_prompt,
            reasoning_effort="none",
            **runtime.generation_params,
        ):
            if not isinstance(chunk, str):
                continue
            visible = think_filter.feed(chunk)
            if visible:
                yield visible

        tail = think_filter.flush()
        if tail:
            yield tail

    async def _resolve_runtime_config(
        self,
        *,
        session_id: str,
        context_type: str,
        project_id: Optional[str],
    ) -> RewriteRuntimeConfig:
        session = await self.storage.get_session(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )

        assistant_id = session.get("assistant_id")
        model_id = session.get("model_id")
        system_prompt: Optional[str] = None
        generation_params: Dict[str, Any] = {}

        if isinstance(assistant_id, str) and assistant_id and not assistant_id.startswith("__legacy_model_"):
            assistant = await AssistantConfigService().get_assistant(assistant_id)
            if assistant:
                system_prompt = assistant.system_prompt
                model_id = assistant.model_id or model_id
                generation_params = self._extract_generation_params(assistant)

        param_overrides = session.get("param_overrides")
        if isinstance(param_overrides, dict):
            override_model_id = param_overrides.get("model_id")
            if isinstance(override_model_id, str) and override_model_id.strip():
                model_id = override_model_id.strip()
            for key in self._PARAM_KEYS:
                if key in param_overrides and param_overrides[key] is not None:
                    generation_params[key] = param_overrides[key]

        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("Session model is unavailable")

        return RewriteRuntimeConfig(
            model_id=model_id.strip(),
            system_prompt=system_prompt,
            generation_params=generation_params,
        )

    def _build_system_prompt(self, assistant_system_prompt: Optional[str]) -> str:
        task_prompt = (
            "You are an expert inline rewrite assistant for a text editor.\n"
            "Rewrite only the selected text according to the instruction and nearby context.\n"
            "Output only the rewritten text.\n"
            "Do not output explanations, markdown fences, headings, or commentary."
        )
        if not assistant_system_prompt:
            return task_prompt
        return f"{assistant_system_prompt}\n\n{task_prompt}"

    def _build_user_prompt(
        self,
        *,
        selected_text: str,
        instruction: Optional[str],
        context_before: str,
        context_after: str,
        file_path: Optional[str],
        language: Optional[str],
    ) -> str:
        rewrite_instruction = (instruction or "").strip() or "Improve clarity while preserving meaning and style."
        file_label = (file_path or "").strip() or "(unknown)"
        language_label = (language or "").strip() or "(unknown)"

        return (
            "Task: Rewrite the selected text based on the instruction.\n"
            f"Instruction: {rewrite_instruction}\n"
            f"File: {file_label}\n"
            f"Language: {language_label}\n\n"
            "<context_before>\n"
            f"{context_before}\n"
            "</context_before>\n\n"
            "<selected_text>\n"
            f"{selected_text}\n"
            "</selected_text>\n\n"
            "<context_after>\n"
            f"{context_after}\n"
            "</context_after>\n\n"
            "Return only the rewritten selected text."
        )

    def _extract_generation_params(self, assistant_obj: Any) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for key in self._PARAM_KEYS:
            value = getattr(assistant_obj, key, None)
            if value is not None:
                params[key] = value
        return params
