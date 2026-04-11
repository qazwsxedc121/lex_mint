"""SiliconFlow OpenAI-compatible adapter implementation."""

import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import BaseMessage

from src.providers.base import BaseLLMAdapter
from src.providers.types import LLMResponse, StreamChunk, TokenUsage

from .reasoning_openai import ChatReasoningOpenAI
from .utils import extract_tool_calls

logger = logging.getLogger(__name__)


class SiliconFlowAdapter(BaseLLMAdapter):
    """Adapter for SiliconFlow OpenAI-compatible API."""

    _DEFAULT_TEST_MODEL = "Qwen/Qwen2.5-7B-Instruct"
    _THINKING_BUDGETS = {"low": 2048, "medium": 4096, "high": 8192}

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
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
        reasoning_effort = kwargs.get("reasoning_effort")
        budget = self._THINKING_BUDGETS.get(
            str(reasoning_effort or "").lower(),
            self._THINKING_BUDGETS["medium"],
        )

        if disable_thinking:
            extra_body["enable_thinking"] = False
            logger.info("SiliconFlow thinking mode disabled for %s", model)
        elif thinking_enabled:
            extra_body["enable_thinking"] = True
            extra_body["thinking_budget"] = budget
            logger.info("SiliconFlow thinking mode enabled for %s (budget=%s)", model, budget)

        for key in ["top_p", "top_k", "frequency_penalty", "presence_penalty", "stop", "seed"]:
            if key in kwargs and kwargs[key] is not None:
                model_kwargs[key] = kwargs[key]
        for key in ["tools", "tool_choice", "parallel_tool_calls", "response_format"]:
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
            tool_calls = extract_tool_calls(chunk)
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
            tool_calls=extract_tool_calls(response),
            usage=usage,
            raw=response,
        )

    def supports_thinking(self) -> bool:
        return True

    def get_thinking_params(self, effort: str = "medium") -> dict[str, Any]:
        budget = self._THINKING_BUDGETS.get(effort, self._THINKING_BUDGETS["medium"])
        return {"enable_thinking": True, "thinking_budget": budget}

    async def fetch_models(self, base_url: str, api_key: str) -> list[dict[str, str]]:
        import httpx

        try:
            models_url = f"{base_url.rstrip('/')}/models"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    models_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"type": "text"},
                )
                response.raise_for_status()
                data = response.json()
                models = []
                for model in data.get("data", []):
                    model_id = model.get("id", "")
                    if not model_id:
                        continue
                    model_type = str(model.get("type", "text")).lower()
                    if model_type and model_type != "text":
                        continue
                    models.append({"id": model_id, "name": model.get("name", model_id)})
                return sorted(models, key=lambda x: x["id"])
        except Exception as exc:
            logger.warning("Failed to fetch SiliconFlow models: %s", exc)
            return []

    async def test_connection(
        self, base_url: str, api_key: str, model_id: str | None = None
    ) -> tuple[bool, str]:
        import httpx

        if not api_key:
            return False, "API key is required"
        try:
            models_url = f"{base_url.rstrip('/')}/models"
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    models_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"type": "text"},
                )
                if response.status_code in (401, 403):
                    return False, "Authentication failed: Invalid API key"
                response.raise_for_status()
                data = response.json()
                if len(data.get("data", [])) > 0:
                    return True, "Connection successful"
                return False, "API responded but returned no models"
        except httpx.TimeoutException:
            return False, "Connection timeout: API not responding"
        except httpx.HTTPStatusError as exc:
            return False, f"HTTP error: {exc.response.status_code}"
        except Exception as exc:
            return False, f"Connection error: {str(exc)}"
