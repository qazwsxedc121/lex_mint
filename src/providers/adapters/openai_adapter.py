"""
OpenAI SDK Adapter

Adapter for OpenAI and OpenAI-compatible APIs (OpenRouter, Groq, Together, etc.)
"""
import logging
from typing import AsyncIterator, List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage

from ..base import BaseLLMAdapter
from ..types import StreamChunk, LLMResponse, TokenUsage
from .utils import extract_tool_calls

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseLLMAdapter):
    """
    Adapter for OpenAI SDK.

    Supports OpenAI API and compatible providers like OpenRouter, Groq, Together AI.
    """

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        **kwargs
    ) -> ChatOpenAI:
        """
        Create a ChatOpenAI instance.

        Args:
            model: Model ID to use
            base_url: API base URL
            api_key: API key for authentication
            temperature: Sampling temperature
            streaming: Whether to enable streaming
            thinking_enabled: Whether to enable reasoning mode (for o1 models)
            **kwargs: Additional parameters passed to ChatOpenAI

        Returns:
            ChatOpenAI instance
        """
        llm_kwargs = {
            "model": model,
            "temperature": temperature,
            "base_url": base_url,
            "api_key": api_key,
            "streaming": streaming,
            "stream_usage": True,
        }

        # For OpenAI o1/o3 models, enable reasoning via responses API
        if thinking_enabled:
            llm_kwargs["reasoning"] = {
                "effort": kwargs.get("reasoning_effort", "medium"),
                "summary": "auto"
            }
            logger.info(f"OpenAI reasoning mode enabled for {model}")

        # Add any extra kwargs
        extra_keys = ["timeout", "max_retries", "max_tokens"]
        for key in extra_keys:
            if key in kwargs:
                llm_kwargs[key] = kwargs[key]

        # Add sampling parameters via model_kwargs
        model_kwargs = {}
        for key in ["top_p", "frequency_penalty", "presence_penalty"]:
            if key in kwargs:
                model_kwargs[key] = kwargs[key]
        if model_kwargs:
            llm_kwargs["model_kwargs"] = model_kwargs

        return ChatOpenAI(**llm_kwargs)

    async def stream(
        self,
        llm: ChatOpenAI,
        messages: List[BaseMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream responses from OpenAI.

        Includes usage data in the final chunk when available.

        Args:
            llm: ChatOpenAI instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects with content
        """
        usage_data = None

        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, 'content') else ""
            thinking = ""

            # Check for reasoning content in additional_kwargs (OpenAI responses API)
            if hasattr(chunk, 'additional_kwargs'):
                thinking = chunk.additional_kwargs.get('reasoning_content', '')

            # Extract usage from chunk (usually only in final chunk)
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
        llm: ChatOpenAI,
        messages: List[BaseMessage],
        **kwargs
    ) -> LLMResponse:
        """
        Invoke OpenAI and get complete response.

        Args:
            llm: ChatOpenAI instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Returns:
            LLMResponse with content
        """
        response = await llm.ainvoke(messages)

        thinking = ""
        if hasattr(response, 'additional_kwargs'):
            thinking = response.additional_kwargs.get('reasoning_content', '')

        usage = None
        if hasattr(response, 'response_metadata'):
            raw_usage = response.response_metadata.get('usage')
            usage = TokenUsage.from_dict(raw_usage)

        return LLMResponse(
            content=response.content,
            thinking=thinking,
            usage=usage,
            raw=response,
        )

    def supports_thinking(self) -> bool:
        """OpenAI o1/o3 models support reasoning."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """Get parameters for OpenAI reasoning mode."""
        return {
            "reasoning": {
                "effort": effort,
                "summary": "auto"
            }
        }

    @staticmethod
    def _parse_model_metadata(model: dict) -> dict | None:
        """
        Parse rich model metadata from provider API responses.

        Detects OpenRouter-style responses (architecture, supported_parameters)
        and extracts capabilities and tags.

        Returns:
            Dict with 'capabilities' and 'tags', or None if no rich metadata.
        """
        architecture = model.get("architecture")
        supported_params = model.get("supported_parameters")
        context_length = model.get("context_length")

        # Only parse if rich metadata is present (e.g. OpenRouter)
        if not architecture and not supported_params and not context_length:
            return None

        input_modalities = (architecture or {}).get("input_modalities", [])
        output_modalities = (architecture or {}).get("output_modalities", [])
        params = supported_params or []

        has_vision = "image" in input_modalities
        has_function_calling = "tools" in params
        has_reasoning = "reasoning" in params or "include_reasoning" in params
        has_image_output = "image" in output_modalities
        has_file_upload = "file" in input_modalities
        has_streaming = True  # Assumed for OpenAI-compatible APIs

        capabilities = {
            "context_length": context_length or 4096,
            "vision": has_vision,
            "function_calling": has_function_calling,
            "reasoning": has_reasoning,
            "streaming": has_streaming,
            "file_upload": has_file_upload,
            "image_output": has_image_output,
        }

        # Derive tags from capabilities
        tags = []
        if has_vision:
            tags.append("vision")
        if has_function_calling:
            tags.append("function-calling")
        if has_reasoning:
            tags.append("reasoning")
        if has_image_output:
            tags.append("image-output")
        if has_file_upload:
            tags.append("file-upload")
        if not tags:
            tags.append("chat")

        return {"capabilities": capabilities, "tags": tags}

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        Fetch available models from OpenAI-compatible API.

        Args:
            base_url: API base URL
            api_key: API key

        Returns:
            List of model info dicts
        """
        import httpx

        try:
            # Normalize base URL
            url = base_url.rstrip('/')
            if not url.endswith('/v1'):
                url = f"{url}/v1"
            models_url = f"{url}/models"

            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    models_url,
                    headers=headers,
                )
                response.raise_for_status()

                data = response.json()
                models = []
                for model in data.get("data", []):
                    model_id = model.get("id", "")
                    entry = {
                        "id": model_id,
                        "name": model.get("name", model_id),
                    }

                    # Parse rich metadata if available (e.g. OpenRouter)
                    caps_and_tags = self._parse_model_metadata(model)
                    if caps_and_tags:
                        entry["capabilities"] = caps_and_tags["capabilities"]
                        entry["tags"] = caps_and_tags["tags"]

                    models.append(entry)

                return sorted(models, key=lambda x: x["id"])

        except Exception as e:
            logger.warning(f"Failed to fetch models: {e}")
            return []
