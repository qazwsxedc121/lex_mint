"""
Zhipu (GLM) OpenAI-Compatible Adapter.

Adapter for Zhipu GLM models via OpenAI-compatible API.
Supports thinking mode, tool calls, tool stream, structured output,
and image understanding through pass-through request parameters.
"""
import logging
from typing import AsyncIterator, List, Dict, Any

from langchain_core.messages import BaseMessage

from .reasoning_openai import ChatReasoningOpenAI
from ..base import BaseLLMAdapter
from ..types import StreamChunk, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)


def _extract_tool_calls(payload: Any) -> List[Any]:
    """Extract tool call payload from LangChain chunks/responses."""
    tool_calls: List[Any] = []

    if hasattr(payload, "tool_calls") and payload.tool_calls:
        tool_calls.extend(payload.tool_calls)

    if hasattr(payload, "tool_call_chunks") and payload.tool_call_chunks:
        tool_calls.extend(payload.tool_call_chunks)

    if hasattr(payload, "additional_kwargs") and payload.additional_kwargs:
        ak = payload.additional_kwargs
        if isinstance(ak, dict):
            ak_tool_calls = ak.get("tool_calls")
            if ak_tool_calls:
                tool_calls.extend(ak_tool_calls)

    return tool_calls


class ZhipuAdapter(BaseLLMAdapter):
    """
    Adapter for Zhipu GLM OpenAI-compatible API.

    Uses ChatReasoningOpenAI (a ChatOpenAI subclass that parses
    reasoning_content) with base_url + api_key, and passes GLM-specific
    capabilities (thinking, tool_stream, response_format, web_search, etc.)
    via extra_body / model_kwargs.
    """

    _CURATED_MODELS: List[Dict[str, str]] = [
        {"id": "glm-5", "name": "GLM-5"},
        {"id": "glm-4.7", "name": "GLM-4.7"},
        {"id": "glm-4.6", "name": "GLM-4.6"},
        {"id": "glm-4.6-flash", "name": "GLM-4.6 Flash"},
        {"id": "glm-4.6v", "name": "GLM-4.6V"},
        {"id": "glm-4.5", "name": "GLM-4.5"},
        {"id": "glm-4.5-air", "name": "GLM-4.5 Air"},
        {"id": "glm-4.5-flash", "name": "GLM-4.5 Flash"},
        {"id": "glm-z1-air", "name": "GLM-Z1 Air"},
        {"id": "glm-z1-airx", "name": "GLM-Z1 AirX"},
    ]

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
        """Create ChatReasoningOpenAI client for Zhipu OpenAI-compatible endpoint."""
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

        # GLM thinking mode uses `thinking.type`.
        # Must go through extra_body since OpenAI SDK rejects unknown params.
        if thinking_enabled:
            extra_body["thinking"] = {"type": "enabled"}
            logger.info(f"Zhipu thinking mode enabled for {model}")

        # Sampling and OpenAI-compatible extras.
        passthrough_keys = [
            "top_p",
            "top_k",
            "frequency_penalty",
            "presence_penalty",
            "stop",
            "seed",
            "user",
            "user_id",
        ]
        for key in passthrough_keys:
            if key in kwargs and kwargs[key] is not None:
                model_kwargs[key] = kwargs[key]

        # GLM capability passthrough (tools, web_search, structured output, etc.).
        feature_keys = [
            "tools",
            "tool_choice",
            "parallel_tool_calls",
            "tool_stream",
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
        """Stream Zhipu responses, including reasoning and tool-call chunks."""
        usage_data = None

        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else ""
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
        self,
        llm: ChatReasoningOpenAI,
        messages: List[BaseMessage],
        **kwargs
    ) -> LLMResponse:
        """Invoke Zhipu and return normalized full response."""
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
            tool_calls=_extract_tool_calls(response),
            usage=usage,
            raw=response,
        )

    def supports_thinking(self) -> bool:
        """GLM supports thinking mode via `thinking.type=enabled`."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """GLM thinking mode is toggle-based, not effort-based."""
        return {"thinking": {"type": "enabled"}}

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        Fetch available models from Zhipu /models endpoint.

        Falls back to curated list on any error.
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
                    if model_id:
                        models.append({
                            "id": model_id,
                            "name": model.get("name", model_id),
                        })

                if models:
                    return sorted(models, key=lambda x: x["id"])

        except Exception as e:
            logger.warning(f"Failed to fetch Zhipu models, using curated list: {e}")

        return sorted(self._CURATED_MODELS, key=lambda x: x["id"])

