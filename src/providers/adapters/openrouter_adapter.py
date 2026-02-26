"""
OpenRouter SDK Adapter

Adapter for OpenRouter API with provider-native reasoning controls.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from .reasoning_openai import inject_tool_call_reasoning_content
from .openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency in CI
    from langchain_openrouter import ChatOpenRouter
except Exception:  # pragma: no cover - fallback keeps app usable without extra package
    ChatOpenRouter = None  # type: ignore[assignment]


if ChatOpenRouter is not None:
    class ChatOpenRouterInterleaved(ChatOpenRouter):
        """ChatOpenRouter wrapper with conditional interleaved payload patching."""

        def _get_request_payload(
            self,
            input_: Any,
            *,
            stop: list[str] | None = None,
            **kwargs: Any,
        ) -> dict:
            payload = super()._get_request_payload(input_, stop=stop, **kwargs)
            source_messages = self._convert_input(input_).to_messages()
            return inject_tool_call_reasoning_content(
                payload,
                source_messages=source_messages,
                enabled=bool(getattr(self, "_requires_interleaved_thinking", False)),
            )
else:
    ChatOpenRouterInterleaved = None  # type: ignore[assignment]


class OpenRouterAdapter(OpenAIAdapter):
    """
    Adapter for OpenRouter via langchain-openrouter.

    Keeps stream/invoke/model-discovery behavior from OpenAIAdapter, but uses
    OpenRouter-native reasoning parameters in `extra_body.reasoning`.
    """

    _DEFAULT_TEST_MODEL = "openai/gpt-4o-mini"

    @staticmethod
    def _build_reasoning_payload(
        *,
        thinking_enabled: bool,
        disable_thinking: bool,
        reasoning_option: str,
        reasoning_effort: str,
    ) -> Dict[str, Any]:
        if disable_thinking:
            return {"enabled": False}
        if not thinking_enabled:
            return {}

        if reasoning_option in {"enabled", "on", "true"}:
            return {"enabled": True}
        if reasoning_option and reasoning_option not in {"disabled", "off", "false", "none"}:
            return {"effort": reasoning_option}

        if reasoning_effort in {"enabled", "on", "true"}:
            return {"enabled": True}
        if reasoning_effort and reasoning_effort not in {"disabled", "off", "false", "none"}:
            return {"effort": reasoning_effort}

        return {"effort": "medium"}

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        **kwargs: Any,
    ) -> Any:
        if ChatOpenRouter is None:
            logger.warning(
                "langchain-openrouter is not installed; falling back to OpenAI-compatible adapter for OpenRouter."
            )
            return super().create_llm(
                model=model,
                base_url=base_url,
                api_key=api_key,
                temperature=temperature,
                streaming=streaming,
                thinking_enabled=thinking_enabled,
                **kwargs,
            )

        llm_kwargs: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "api_key": api_key,
            "streaming": streaming,
            "stream_usage": True,
        }

        # Keep base_url configurable for proxies / enterprise routing.
        if base_url:
            llm_kwargs["base_url"] = base_url

        disable_thinking = bool(kwargs.get("disable_thinking", False))
        reasoning_option = str(kwargs.get("reasoning_option") or "").strip().lower()
        reasoning_effort = str(kwargs.get("reasoning_effort") or "").strip().lower()

        extra_body = dict(kwargs.get("extra_body") or {})
        reasoning_payload = self._build_reasoning_payload(
            thinking_enabled=thinking_enabled,
            disable_thinking=disable_thinking,
            reasoning_option=reasoning_option,
            reasoning_effort=reasoning_effort,
        )
        if reasoning_payload:
            extra_body["reasoning"] = reasoning_payload
            logger.info("OpenRouter reasoning mode set for %s: %s", model, reasoning_payload)
        if extra_body:
            llm_kwargs["extra_body"] = extra_body

        for key in ("timeout", "max_retries", "max_tokens"):
            if key in kwargs:
                llm_kwargs[key] = kwargs[key]

        model_kwargs = {}
        for key in ("top_p", "frequency_penalty", "presence_penalty"):
            if key in kwargs:
                model_kwargs[key] = kwargs[key]
        if model_kwargs:
            llm_kwargs["model_kwargs"] = model_kwargs

        requires_interleaved = bool(kwargs.get("requires_interleaved_thinking", False))
        llm_cls = ChatOpenRouterInterleaved if (requires_interleaved and ChatOpenRouterInterleaved) else ChatOpenRouter
        llm = llm_cls(**llm_kwargs)
        if requires_interleaved:
            object.__setattr__(llm, "_requires_interleaved_thinking", True)
        return llm
