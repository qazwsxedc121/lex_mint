"""
Moonshot (Kimi) OpenAI-Compatible Adapter.

Adapter for Kimi models via Moonshot's OpenAI-compatible API.
Includes K2.5-specific thinking and parameter normalization rules.
"""
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .reasoning_openai import ChatReasoningOpenAI, inject_tool_call_reasoning_content
from .utils import extract_tool_calls
from ..base import BaseLLMAdapter
from ..types import LLMResponse, StreamChunk, TokenUsage

logger = logging.getLogger(__name__)


def _response_content_to_text(content: object) -> str:
    """Normalize LangChain response content into plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
        return "".join(parts)
    return str(content or "")


class KimiAdapter(BaseLLMAdapter):
    """Adapter for Moonshot Kimi OpenAI-compatible API."""

    _DEFAULT_TEST_MODEL = "kimi-k2.5"

    @staticmethod
    def _is_k2_5_model(model: str) -> bool:
        """Return whether the model belongs to the K2.5 family."""
        return str(model or "").strip().lower().startswith("kimi-k2.5")

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        **kwargs
    ) -> "ChatKimiOpenAI":
        """Create ChatReasoningOpenAI client for Kimi endpoint."""
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
        is_k2_5_model = self._is_k2_5_model(model)

        normalized_temperature = temperature
        normalized_top_p = kwargs.get("top_p")
        normalized_frequency_penalty = kwargs.get("frequency_penalty")
        normalized_presence_penalty = kwargs.get("presence_penalty")
        normalized_n = kwargs.get("n")
        normalized_tool_choice = kwargs.get("tool_choice")

        if is_k2_5_model:
            if disable_thinking:
                extra_body["thinking"] = {"type": "disabled"}
                normalized_temperature = 0.6
                logger.info("Kimi K2.5 thinking mode disabled for %s", model)
            else:
                if thinking_enabled:
                    extra_body["thinking"] = {"type": "enabled"}
                    logger.info("Kimi K2.5 thinking mode enabled for %s", model)
                normalized_temperature = 1.0

            if temperature != normalized_temperature:
                logger.info(
                    "Kimi K2.5 normalized temperature for %s: %s -> %s",
                    model,
                    temperature,
                    normalized_temperature,
                )

            normalized_top_p = 0.95
            normalized_frequency_penalty = 0.0
            normalized_presence_penalty = 0.0

            if normalized_n not in (None, 1):
                logger.warning(
                    "Kimi K2.5 normalized n for %s: %s -> 1",
                    model,
                    normalized_n,
                )
                normalized_n = 1

            if not disable_thinking and normalized_tool_choice is not None:
                tool_choice_value = str(normalized_tool_choice).strip().lower()
                if tool_choice_value not in {"auto", "none"}:
                    logger.warning(
                        "Kimi K2.5 normalized tool_choice for %s: %s -> auto",
                        model,
                        normalized_tool_choice,
                    )
                    normalized_tool_choice = "auto"

        llm_kwargs["temperature"] = normalized_temperature

        passthrough_keys = [
            "top_k",
            "stop",
            "seed",
            "user",
            "parallel_tool_calls",
            "response_format",
            "stream_options",
        ]
        for key in passthrough_keys:
            if key in kwargs and kwargs[key] is not None:
                model_kwargs[key] = kwargs[key]

        if normalized_top_p is not None:
            model_kwargs["top_p"] = normalized_top_p
        if normalized_frequency_penalty is not None:
            model_kwargs["frequency_penalty"] = normalized_frequency_penalty
        if normalized_presence_penalty is not None:
            model_kwargs["presence_penalty"] = normalized_presence_penalty
        if normalized_n is not None:
            model_kwargs["n"] = normalized_n
        if "tools" in kwargs and kwargs["tools"] is not None:
            model_kwargs["tools"] = kwargs["tools"]
        if normalized_tool_choice is not None:
            model_kwargs["tool_choice"] = normalized_tool_choice

        if extra_body:
            llm_kwargs["extra_body"] = extra_body
        if model_kwargs:
            llm_kwargs["model_kwargs"] = model_kwargs

        llm = ChatKimiOpenAI(**llm_kwargs)
        object.__setattr__(
            llm,
            "_requires_interleaved_thinking",
            bool(kwargs.get("requires_interleaved_thinking", False)),
        )
        return llm

    async def stream(
        self,
        llm: "ChatKimiOpenAI",
        messages: List[BaseMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Stream Kimi responses, including reasoning and tool-call chunks."""
        usage_data = None

        async for chunk in llm.astream(messages):
            content = _response_content_to_text(chunk.content if hasattr(chunk, "content") else "")
            thinking = ""

            if hasattr(chunk, "additional_kwargs") and chunk.additional_kwargs:
                thinking = chunk.additional_kwargs.get("reasoning_content", "")

            extracted = TokenUsage.extract_from_chunk(chunk)
            if extracted:
                usage_data = extracted

            yield StreamChunk(
                content=content,
                thinking=thinking,
                tool_calls=extract_tool_calls(chunk),
                usage=usage_data,
                raw=chunk,
            )

    async def invoke(
        self,
        llm: "ChatKimiOpenAI",
        messages: List[BaseMessage],
        **kwargs
    ) -> LLMResponse:
        """Invoke Kimi and return normalized full response."""
        response = await llm.ainvoke(messages)

        thinking = ""
        if hasattr(response, "additional_kwargs") and response.additional_kwargs:
            thinking = response.additional_kwargs.get("reasoning_content", "")

        usage = None
        if hasattr(response, "response_metadata") and response.response_metadata:
            usage = TokenUsage.from_dict(response.response_metadata.get("usage"))

        return LLMResponse(
            content=_response_content_to_text(response.content),
            thinking=thinking,
            tool_calls=extract_tool_calls(response),
            usage=usage,
            raw=response,
        )

    def supports_thinking(self) -> bool:
        """Kimi supports thinking mode on compatible models."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """Kimi thinking mode is toggle-based, not effort-based."""
        return {"thinking": {"type": "enabled"}}

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        Fetch available models from Kimi /models endpoint.

        Returns an empty list on errors (no static fallback list).
        """
        import httpx

        try:
            url = base_url.rstrip("/")
            if not url.endswith("/v1"):
                url = f"{url}/v1"
            models_url = f"{url}/models"

            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(models_url, headers=headers)
                response.raise_for_status()

                data = response.json()
                models = []
                for model in data.get("data", []):
                    model_id = model.get("id", "")
                    if not model_id:
                        continue
                    models.append({
                        "id": model_id,
                        "name": model.get("name", model_id),
                    })

                return sorted(models, key=lambda x: x["id"])
        except Exception as e:
            logger.warning("Failed to fetch Kimi models: %s", e)
            return []

    async def test_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Test Kimi connection via model-list endpoint.

        Uses /v1/models to validate auth and connectivity without generation cost.
        """
        import httpx

        if not api_key:
            return False, "API key is required"

        try:
            url = base_url.rstrip("/")
            if not url.endswith("/v1"):
                url = f"{url}/v1"
            models_url = f"{url}/models"

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    models_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                )

                if response.status_code in (401, 403):
                    return False, "Authentication failed: Invalid API key"
                if response.status_code == 404:
                    return False, "API endpoint not found: Check base URL"

                response.raise_for_status()
                data = response.json()

                if len(data.get("data", [])) > 0:
                    return True, "Connection successful"
                return False, "API responded but returned no models"

        except httpx.TimeoutException:
            return False, "Connection timeout: API not responding"
        except httpx.HTTPStatusError as e:
            return False, f"HTTP error: {e.response.status_code}"
        except Exception as e:
            return False, f"Connection error: {str(e)}"


class ChatKimiOpenAI(ChatReasoningOpenAI):
    """
    Kimi-specific ChatOpenAI wrapper.

    LangChain's default message conversion drops unknown assistant fields.
    Kimi thinking + tool-calls requires assistant tool-call messages to include
    `reasoning_content`, so we patch the outgoing payload accordingly.
    """

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
