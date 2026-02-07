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
                    models.append({
                        "id": model_id,
                        "name": model.get("name", model_id),
                    })

                return sorted(models, key=lambda x: x["id"])

        except Exception as e:
            logger.warning(f"Failed to fetch models: {e}")
            return []
