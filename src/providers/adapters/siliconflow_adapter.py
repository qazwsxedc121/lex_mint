"""
SiliconFlow OpenAI-Compatible Adapter.

Adapter for SiliconFlow models via OpenAI-compatible API.
Supports thinking mode (`enable_thinking`, `thinking_budget`), tool calls,
and streaming through pass-through request parameters.
"""
import logging
from typing import AsyncIterator, List, Dict, Any, Optional

from langchain_core.messages import BaseMessage

from .reasoning_openai import ChatReasoningOpenAI
from .utils import extract_tool_calls
from ..base import BaseLLMAdapter
from ..types import StreamChunk, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)


class SiliconFlowAdapter(BaseLLMAdapter):
    """
    Adapter for SiliconFlow OpenAI-compatible API.

    Uses ChatReasoningOpenAI so reasoning_content can be surfaced when present.
    """

    _DEFAULT_TEST_MODEL = "Qwen/Qwen2.5-7B-Instruct"

    _THINKING_BUDGETS = {
        "low": 2048,
        "medium": 4096,
        "high": 8192,
    }

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        **kwargs
    ) -> ChatReasoningOpenAI:
        """Create ChatReasoningOpenAI client for SiliconFlow endpoint."""
        llm_kwargs: Dict[str, Any] = {
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

        model_kwargs: Dict[str, Any] = {}
        extra_body: Dict[str, Any] = {}

        disable_thinking = bool(kwargs.get("disable_thinking", False))
        reasoning_effort = kwargs.get("reasoning_effort")
        budget = self._THINKING_BUDGETS.get(str(reasoning_effort or "").lower(), self._THINKING_BUDGETS["medium"])

        if disable_thinking:
            extra_body["enable_thinking"] = False
            logger.info("SiliconFlow thinking mode disabled for %s", model)
        elif thinking_enabled:
            extra_body["enable_thinking"] = True
            extra_body["thinking_budget"] = budget
            logger.info("SiliconFlow thinking mode enabled for %s (budget=%s)", model, budget)

        passthrough_keys = [
            "top_p",
            "top_k",
            "frequency_penalty",
            "presence_penalty",
            "stop",
            "seed",
        ]
        for key in passthrough_keys:
            if key in kwargs and kwargs[key] is not None:
                model_kwargs[key] = kwargs[key]

        feature_keys = [
            "tools",
            "tool_choice",
            "parallel_tool_calls",
            "response_format",
        ]
        for key in feature_keys:
            if key in kwargs and kwargs[key] is not None:
                model_kwargs[key] = kwargs[key]

        if extra_body:
            llm_kwargs["extra_body"] = extra_body
        if model_kwargs:
            llm_kwargs["model_kwargs"] = model_kwargs

        return ChatReasoningOpenAI(**llm_kwargs)

    async def stream(
        self,
        llm: ChatReasoningOpenAI,
        messages: List[BaseMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Stream SiliconFlow responses, including reasoning and tool-call chunks."""
        usage_data = None

        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else ""
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
        self,
        llm: ChatReasoningOpenAI,
        messages: List[BaseMessage],
        **kwargs
    ) -> LLMResponse:
        """Invoke SiliconFlow and return normalized full response."""
        response = await llm.ainvoke(messages)

        thinking = ""
        if hasattr(response, "additional_kwargs") and response.additional_kwargs:
            thinking = response.additional_kwargs.get("reasoning_content", "")

        usage = None
        if hasattr(response, "response_metadata") and response.response_metadata:
            usage = TokenUsage.from_dict(response.response_metadata.get("usage"))

        return LLMResponse(
            content=response.content,
            thinking=thinking,
            tool_calls=extract_tool_calls(response),
            usage=usage,
            raw=response,
        )

    def supports_thinking(self) -> bool:
        """SiliconFlow supports thinking mode on compatible models."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """Map reasoning effort to SiliconFlow thinking parameters."""
        budget = self._THINKING_BUDGETS.get(effort, self._THINKING_BUDGETS["medium"])
        return {
            "enable_thinking": True,
            "thinking_budget": budget,
        }

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        Fetch available text models from SiliconFlow /models endpoint.

        Uses `type=text` query to avoid mixing image/audio/video model IDs.
        """
        import httpx

        try:
            url = base_url.rstrip("/")
            models_url = f"{url}/models"

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

                    models.append({
                        "id": model_id,
                        "name": model.get("name", model_id),
                    })

                return sorted(models, key=lambda x: x["id"])

        except Exception as e:
            logger.warning(f"Failed to fetch SiliconFlow models: {e}")
            return []

    async def test_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: str = None
    ) -> tuple[bool, str]:
        """
        Test connection via lightweight model-list call (no generation quota).
        """
        import httpx

        if not api_key:
            return False, "API key is required"

        try:
            url = base_url.rstrip("/")
            models_url = f"{url}/models"

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
                model_count = len(data.get("data", []))
                if model_count > 0:
                    return True, "Connection successful"
                return False, "API responded but returned no models"

        except httpx.TimeoutException:
            return False, "Connection timeout: API not responding"
        except httpx.HTTPStatusError as e:
            return False, f"HTTP error: {e.response.status_code}"
        except Exception as e:
            return False, f"Connection error: {str(e)}"
