"""
Volcano Engine (Doubao) OpenAI-Compatible Adapter.

Adapter for Doubao models via Volcano Engine Ark platform's OpenAI-compatible API.
Supports thinking mode, reasoning effort levels, tool calls, and streaming
through pass-through request parameters.
"""
import logging
from typing import AsyncIterator, List, Dict, Any, Optional

from langchain_core.messages import BaseMessage

from .reasoning_openai import ChatReasoningOpenAI
from .utils import extract_tool_calls
from ..base import BaseLLMAdapter
from ..types import StreamChunk, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)


class VolcEngineAdapter(BaseLLMAdapter):
    """
    Adapter for Volcano Engine (Doubao) OpenAI-compatible API.

    Uses ChatReasoningOpenAI (a ChatOpenAI subclass that parses
    reasoning_content) with the Ark platform base_url + api_key, and passes
    Doubao-specific capabilities (thinking, reasoning_effort, etc.)
    via extra_body / model_kwargs.
    """

    _CURATED_MODELS: List[Dict[str, str]] = [
        {"id": "doubao-seed-2-0-pro-260215", "name": "Doubao Seed 2.0 Pro"},
        {"id": "doubao-seed-2-0-lite-260215", "name": "Doubao Seed 2.0 Lite"},
        {"id": "doubao-seed-2-0-mini-260215", "name": "Doubao Seed 2.0 Mini"},
        {"id": "doubao-seed-2-0-code-preview-260215", "name": "Doubao Seed 2.0 Code"},
        {"id": "doubao-1-5-pro-256k-250115", "name": "Doubao 1.5 Pro 256K"},
        {"id": "doubao-1-5-pro-32k-250115", "name": "Doubao 1.5 Pro 32K"},
    ]

    # Volcengine supports 4-level reasoning effort
    _EFFORT_LEVELS = {"minimal", "low", "medium", "high"}

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        reasoning_effort: Optional[str] = None,
        **kwargs
    ) -> ChatReasoningOpenAI:
        """Create ChatReasoningOpenAI client for Volcano Engine Ark endpoint."""
        llm_kwargs: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "base_url": base_url,
            "api_key": api_key,
            "streaming": streaming,
            "stream_usage": True,
        }

        # Common direct parameters ChatOpenAI already supports.
        for key in ["timeout", "max_retries", "max_tokens"]:
            if key in kwargs and kwargs[key] is not None:
                llm_kwargs[key] = kwargs[key]

        model_kwargs: Dict[str, Any] = {}
        extra_body: Dict[str, Any] = {}

        # Doubao thinking mode uses `thinking.type`.
        # Must go through extra_body since OpenAI SDK rejects unknown params.
        if thinking_enabled:
            extra_body["thinking"] = {"type": "enabled"}
            logger.info(f"Volcengine thinking mode enabled for {model}")

        # Reasoning effort (Volcengine supports minimal/low/medium/high).
        if reasoning_effort:
            if reasoning_effort in self._EFFORT_LEVELS:
                extra_body["reasoning_effort"] = reasoning_effort
                logger.info(f"Volcengine reasoning_effort={reasoning_effort} for {model}")
            else:
                logger.warning(
                    f"Invalid reasoning_effort '{reasoning_effort}' for Volcengine. "
                    f"Valid: {self._EFFORT_LEVELS}. Ignoring."
                )

        # Sampling and OpenAI-compatible extras.
        passthrough_keys = [
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "stop",
            "seed",
        ]
        for key in passthrough_keys:
            if key in kwargs and kwargs[key] is not None:
                model_kwargs[key] = kwargs[key]

        # Feature passthrough (tools, etc.).
        feature_keys = [
            "tools",
            "tool_choice",
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
        """Stream Volcengine responses, including reasoning and tool-call chunks."""
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
        """Invoke Volcengine and return normalized full response."""
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
        """Doubao supports thinking mode via `thinking.type=enabled`."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """
        Doubao supports both thinking toggle and reasoning effort levels.

        Args:
            effort: Reasoning effort level (minimal, low, medium, high)

        Returns:
            Dict with thinking and reasoning_effort parameters
        """
        effort_value = effort if effort in self._EFFORT_LEVELS else "medium"
        return {
            "thinking": {"type": "enabled"},
            "reasoning_effort": effort_value,
        }

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        Fetch available models from Volcengine /models endpoint.

        Filters to active models only. Falls back to curated list on any error.
        """
        import httpx

        try:
            url = base_url.rstrip("/")
            models_url = f"{url}/models"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    models_url,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                response.raise_for_status()

                data = response.json()
                models = []
                for model in data.get("data", []):
                    model_id = model.get("id", "")
                    if not model_id:
                        continue

                    # Only include active models
                    status = model.get("status", "").lower()
                    if status and status != "active":
                        continue

                    name = model.get("name", model_id)
                    models.append({"id": model_id, "name": name})

                if models:
                    return sorted(models, key=lambda x: x["id"])

        except Exception as e:
            logger.warning(f"Failed to fetch Volcengine models, using curated list: {e}")

        return sorted(self._CURATED_MODELS, key=lambda x: x["id"])
