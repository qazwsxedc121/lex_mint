"""VolcEngine (Doubao) OpenAI-compatible adapter implementation."""

import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import BaseMessage

from src.providers.base import BaseLLMAdapter
from src.providers.types import LLMResponse, StreamChunk, TokenUsage

from .reasoning_openai import ChatReasoningOpenAI

logger = logging.getLogger(__name__)


def _extract_tool_calls(payload: Any) -> list[Any]:
    if hasattr(payload, "tool_call_chunks") and payload.tool_call_chunks:
        return list(payload.tool_call_chunks)
    if hasattr(payload, "tool_calls") and payload.tool_calls:
        return list(payload.tool_calls)
    if hasattr(payload, "additional_kwargs") and payload.additional_kwargs:
        ak = payload.additional_kwargs
        if isinstance(ak, dict):
            ak_tool_calls = ak.get("tool_calls")
            if ak_tool_calls:
                return list(ak_tool_calls)
    return []


class VolcEngineAdapter(BaseLLMAdapter):
    """Adapter for Volcano Engine (Doubao) OpenAI-compatible API."""

    _DEFAULT_TEST_MODEL = "doubao-1-5-pro-32k-250115"
    _CURATED_MODELS: list[dict[str, str]] = [
        {"id": "doubao-seed-2-0-pro-260215", "name": "Doubao Seed 2.0 Pro"},
        {"id": "doubao-seed-2-0-lite-260215", "name": "Doubao Seed 2.0 Lite"},
        {"id": "doubao-seed-2-0-mini-260215", "name": "Doubao Seed 2.0 Mini"},
        {"id": "doubao-seed-2-0-code-preview-260215", "name": "Doubao Seed 2.0 Code"},
        {"id": "doubao-1-5-pro-256k-250115", "name": "Doubao 1.5 Pro 256K"},
        {"id": "doubao-1-5-pro-32k-250115", "name": "Doubao 1.5 Pro 32K"},
    ]
    _EFFORT_LEVELS = {"minimal", "low", "medium", "high"}

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        reasoning_effort: str | None = None,
        **kwargs,
    ) -> ChatReasoningOpenAI:
        llm_kwargs: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "base_url": base_url,
            "api_key": api_key,
            "streaming": streaming,
            "stream_usage": True,
        }
        for key in ["timeout", "max_retries", "max_tokens"]:
            if key in kwargs and kwargs[key] is not None:
                llm_kwargs[key] = kwargs[key]

        model_kwargs: dict[str, Any] = {}
        extra_body: dict[str, Any] = {}
        disable_thinking = bool(kwargs.get("disable_thinking", False))

        if disable_thinking:
            extra_body["thinking"] = {"type": "disabled"}
            logger.info("Volcengine thinking mode disabled for %s", model)
        elif thinking_enabled:
            extra_body["thinking"] = {"type": "enabled"}
            logger.info("Volcengine thinking mode enabled for %s", model)

        if reasoning_effort and not disable_thinking:
            if reasoning_effort in self._EFFORT_LEVELS:
                extra_body["reasoning_effort"] = reasoning_effort
                logger.info("Volcengine reasoning_effort=%s for %s", reasoning_effort, model)
            else:
                logger.warning(
                    "Invalid reasoning_effort '%s' for Volcengine. Valid: %s. Ignoring.",
                    reasoning_effort,
                    self._EFFORT_LEVELS,
                )
        elif reasoning_effort and disable_thinking:
            logger.info("Volcengine reasoning_effort ignored because thinking is disabled for %s", model)

        for key in ["top_p", "frequency_penalty", "presence_penalty", "stop", "seed"]:
            if key in kwargs and kwargs[key] is not None:
                model_kwargs[key] = kwargs[key]

        for key in ["tools", "tool_choice"]:
            if key in kwargs and kwargs[key] is not None:
                model_kwargs[key] = kwargs[key]

        if extra_body:
            llm_kwargs["extra_body"] = extra_body
        if model_kwargs:
            llm_kwargs["model_kwargs"] = model_kwargs
        return ChatReasoningOpenAI(**llm_kwargs)

    async def stream(
        self, llm: ChatReasoningOpenAI, messages: list[BaseMessage], **kwargs
    ) -> AsyncIterator[StreamChunk]:
        usage_data = None
        async for chunk in llm.astream(messages):
            content_raw = chunk.content if hasattr(chunk, "content") else ""
            content = content_raw if isinstance(content_raw, str) else str(content_raw or "")
            thinking = ""
            tool_calls = _extract_tool_calls(chunk)
            if hasattr(chunk, "additional_kwargs") and chunk.additional_kwargs:
                thinking = chunk.additional_kwargs.get("reasoning_content", "")
            extracted = TokenUsage.extract_from_chunk(chunk)
            if extracted:
                usage_data = extracted
            yield StreamChunk(
                content=content,
                thinking=thinking,
                tool_calls=tool_calls,
                usage=usage_data,
                raw=chunk,
            )

    async def invoke(
        self, llm: ChatReasoningOpenAI, messages: list[BaseMessage], **kwargs
    ) -> LLMResponse:
        response = await llm.ainvoke(messages)
        thinking = ""
        if hasattr(response, "additional_kwargs") and response.additional_kwargs:
            thinking = response.additional_kwargs.get("reasoning_content", "")
        usage = None
        if hasattr(response, "response_metadata") and response.response_metadata:
            usage = TokenUsage.from_dict(response.response_metadata.get("usage"))
        content_raw = response.content if hasattr(response, "content") else ""
        content = content_raw if isinstance(content_raw, str) else str(content_raw or "")
        return LLMResponse(
            content=content,
            thinking=thinking,
            tool_calls=_extract_tool_calls(response),
            usage=usage,
            raw=response,
        )

    def supports_thinking(self) -> bool:
        return True

    def get_thinking_params(self, effort: str = "medium") -> dict[str, Any]:
        effort_value = effort if effort in self._EFFORT_LEVELS else "medium"
        return {"thinking": {"type": "enabled"}, "reasoning_effort": effort_value}

    async def fetch_models(self, base_url: str, api_key: str) -> list[dict[str, str]]:
        import httpx

        try:
            models_url = f"{base_url.rstrip('/')}/models"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    models_url, headers={"Authorization": f"Bearer {api_key}"}
                )
                response.raise_for_status()
                data = response.json()
                models = []
                for model in data.get("data", []):
                    model_id = model.get("id", "")
                    if not model_id:
                        continue
                    status = model.get("status", "").lower()
                    if status and status != "active":
                        continue
                    models.append({"id": model_id, "name": model.get("name", model_id)})
                if models:
                    return sorted(models, key=lambda x: x["id"])
        except Exception as exc:
            logger.warning("Failed to fetch Volcengine models, using curated list: %s", exc)

        return sorted(self._CURATED_MODELS, key=lambda x: x["id"])
