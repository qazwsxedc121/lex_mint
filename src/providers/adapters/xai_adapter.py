"""
xAI (Grok) SDK Adapter

Adapter for xAI Grok API with Live Search and reasoning support.
"""
import logging
from typing import AsyncIterator, List, Dict, Any
from langchain_core.messages import BaseMessage

from ..base import BaseLLMAdapter
from ..types import StreamChunk, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)


class XAIAdapter(BaseLLMAdapter):
    """
    Adapter for xAI Grok SDK.

    Uses langchain-xai package for proper reasoning_content and Live Search support.
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
    ):
        """
        Create a ChatXAI instance.

        Args:
            model: Model ID (grok-4, grok-3, etc.)
            base_url: API base URL
            api_key: API key
            temperature: Sampling temperature
            streaming: Whether to enable streaming
            thinking_enabled: Whether to enable thinking mode
            **kwargs: Additional parameters (live_search, etc.)

        Returns:
            ChatXAI instance
        """
        from langchain_xai import ChatXAI

        llm_kwargs = {
            "model": model,
            "xai_api_key": api_key,
            "xai_api_base": base_url,
            "streaming": streaming,
            "temperature": temperature,
        }

        # Enable Live Search if requested
        if kwargs.get("live_search"):
            llm_kwargs["live_search"] = True
            logger.info(f"xAI Live Search enabled for {model}")

        # Add max_tokens as direct param
        if "max_tokens" in kwargs:
            llm_kwargs["max_tokens"] = kwargs["max_tokens"]

        # Add sampling parameters via model_kwargs
        model_kwargs = {}
        for key in ["top_p", "frequency_penalty", "presence_penalty"]:
            if key in kwargs:
                model_kwargs[key] = kwargs[key]
        if model_kwargs:
            llm_kwargs["model_kwargs"] = model_kwargs

        return ChatXAI(**llm_kwargs)

    async def stream(
        self,
        llm,
        messages: List[BaseMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream responses from xAI Grok.

        Properly handles reasoning_content field for thinking mode.
        Includes usage data in the final chunk when available.

        Args:
            llm: ChatXAI instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects with content and thinking
        """
        usage_data = None

        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, 'content') else ""
            thinking = ""

            # Grok returns reasoning_content in additional_kwargs
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
        llm,
        messages: List[BaseMessage],
        **kwargs
    ) -> LLMResponse:
        """
        Invoke xAI Grok and get complete response.

        Args:
            llm: ChatXAI instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Returns:
            LLMResponse with content and thinking
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
        """xAI Grok supports thinking mode."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """
        Get parameters for Grok thinking mode.

        Note: Grok doesn't use effort levels, it's either enabled or disabled.
        """
        return {}

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        xAI doesn't support model listing API.

        Returns pre-defined models.
        """
        return [
            {"id": "grok-4", "name": "Grok 4"},
            {"id": "grok-4-fast", "name": "Grok 4.1 Fast"},
            {"id": "grok-3", "name": "Grok 3"},
            {"id": "grok-3-mini", "name": "Grok 3 Mini"},
        ]
