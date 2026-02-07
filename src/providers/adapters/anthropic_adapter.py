"""
Anthropic SDK Adapter

Adapter for Anthropic Claude API using langchain-anthropic.
"""
import logging
from typing import AsyncIterator, List, Dict, Any

from langchain_core.messages import BaseMessage

from ..base import BaseLLMAdapter
from ..types import StreamChunk, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)


class AnthropicAdapter(BaseLLMAdapter):
    """
    Adapter for Anthropic Claude SDK.

    Uses langchain-anthropic package for proper Claude API integration.
    Supports extended thinking for Claude models.
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
        Create a ChatAnthropic instance.

        Args:
            model: Model ID (claude-sonnet-4-5-20250929, etc.)
            base_url: API base URL
            api_key: API key
            temperature: Sampling temperature
            streaming: Whether to enable streaming
            thinking_enabled: Whether to enable extended thinking
            **kwargs: Additional parameters

        Returns:
            ChatAnthropic instance
        """
        from langchain_anthropic import ChatAnthropic

        llm_kwargs = {
            "model": model,
            "api_key": api_key,
            "streaming": streaming,
            "temperature": temperature,
        }

        # Set base URL if not default
        if base_url and base_url != "https://api.anthropic.com":
            llm_kwargs["base_url"] = base_url

        # Enable extended thinking if requested
        if thinking_enabled:
            llm_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": kwargs.get("thinking_budget", 10000)
            }
            # Extended thinking doesn't support temperature
            llm_kwargs.pop("temperature", None)
            logger.info(f"Anthropic extended thinking enabled for {model}")

        # Add sampling parameters (ChatAnthropic accepts these directly)
        if "top_p" in kwargs:
            llm_kwargs["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            llm_kwargs["top_k"] = kwargs["top_k"]

        # Add max_tokens if specified
        if "max_tokens" in kwargs:
            llm_kwargs["max_tokens"] = kwargs["max_tokens"]
        elif thinking_enabled:
            # Extended thinking requires max_tokens
            llm_kwargs["max_tokens"] = kwargs.get("max_tokens", 16000)

        return ChatAnthropic(**llm_kwargs)

    async def stream(
        self,
        llm,
        messages: List[BaseMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream responses from Anthropic Claude.

        Properly handles thinking content for extended thinking mode.
        Includes usage data in the final chunk when available.

        Args:
            llm: ChatAnthropic instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects with content and thinking
        """
        usage_data = None

        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, 'content') else ""
            thinking = ""

            # Check for thinking content in additional_kwargs
            if hasattr(chunk, 'additional_kwargs'):
                thinking = chunk.additional_kwargs.get('thinking', '')
                if not thinking:
                    thinking = chunk.additional_kwargs.get('thinking_content', '')

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
        Invoke Anthropic Claude and get complete response.

        Args:
            llm: ChatAnthropic instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Returns:
            LLMResponse with content and thinking
        """
        response = await llm.ainvoke(messages)

        thinking = ""
        if hasattr(response, 'additional_kwargs'):
            thinking = response.additional_kwargs.get('thinking', '')
            if not thinking:
                thinking = response.additional_kwargs.get('thinking_content', '')

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
        """Claude supports extended thinking."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """
        Get parameters for Claude extended thinking mode.

        Maps effort levels to budget tokens:
        - low: 5000 tokens
        - medium: 10000 tokens
        - high: 20000 tokens
        """
        budget_map = {
            "low": 5000,
            "medium": 10000,
            "high": 20000,
        }
        return {
            "thinking": {
                "type": "enabled",
                "budget_tokens": budget_map.get(effort, 10000)
            }
        }

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        Anthropic doesn't provide a public model listing API.

        Returns pre-defined models based on official documentation.
        """
        return [
            {"id": "claude-sonnet-4-5-20250929", "name": "Claude Sonnet 4.5"},
            {"id": "claude-opus-4-5-20251101", "name": "Claude Opus 4.5"},
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
            {"id": "claude-haiku-4-5-20250630", "name": "Claude Haiku 4.5"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet (Legacy)"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus (Legacy)"},
            {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku (Legacy)"},
        ]
