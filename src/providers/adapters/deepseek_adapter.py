"""
DeepSeek SDK Adapter

Adapter for DeepSeek API with proper reasoning_content support.
"""
import logging
from typing import AsyncIterator, List, Dict, Any
from langchain_core.messages import AIMessage, BaseMessage
from langchain_deepseek import ChatDeepSeek

from ..base import BaseLLMAdapter
from ..types import StreamChunk, LLMResponse, TokenUsage
from .utils import extract_tool_calls

logger = logging.getLogger(__name__)


class ChatDeepSeekInterleaved(ChatDeepSeek):
    """
    DeepSeek wrapper to preserve interleaved reasoning for tool-call messages.

    Some model/tool-call paths require `reasoning_content` to be present on
    assistant tool-call messages in subsequent rounds.
    """

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)

        payload_messages = payload.get("messages")
        if not isinstance(payload_messages, list):
            return payload

        source_messages = self._convert_input(input_).to_messages()
        for msg_obj, msg_dict in zip(source_messages, payload_messages):
            if not isinstance(msg_obj, AIMessage):
                continue
            if not isinstance(msg_dict, dict) or msg_dict.get("role") != "assistant":
                continue
            if "tool_calls" not in msg_dict:
                continue

            reasoning_content = msg_obj.additional_kwargs.get("reasoning_content")
            if reasoning_content:
                msg_dict["reasoning_content"] = reasoning_content

        return payload


class DeepSeekAdapter(BaseLLMAdapter):
    """
    Adapter for DeepSeek SDK.

    Uses langchain-deepseek package for proper reasoning_content handling.
    """

    _DEFAULT_TEST_MODEL = "deepseek-chat"

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
        Create a ChatDeepSeek instance.

        Args:
            model: Model ID (deepseek-chat, deepseek-reasoner, etc.)
            base_url: API base URL
            api_key: API key
            temperature: Sampling temperature
            streaming: Whether to enable streaming
            thinking_enabled: Whether to enable thinking mode
            **kwargs: Additional parameters

        Returns:
            ChatDeepSeek instance
        """
        llm_kwargs = {
            "model": model,
            "api_key": api_key,
            "api_base": base_url,
            "streaming": streaming,
            "stream_usage": True,
        }
        disable_thinking = bool(kwargs.get("disable_thinking", False))

        # DeepSeek thinking mode uses `thinking.type` in extra_body.
        # Use explicit disabled mode for reasoning_effort="none".
        if disable_thinking:
            llm_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            llm_kwargs["temperature"] = temperature
            logger.info(f"DeepSeek thinking mode disabled for {model}")
        elif thinking_enabled:
            llm_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            # Thinking mode doesn't support temperature
            logger.info(f"DeepSeek thinking mode enabled for {model}")
        else:
            llm_kwargs["temperature"] = temperature

        # Add max_tokens as direct param
        if "max_tokens" in kwargs:
            llm_kwargs["max_tokens"] = kwargs["max_tokens"]

        # Add sampling parameters via model_kwargs.
        extra_model_kwargs = {}
        for key in ["top_p", "frequency_penalty", "presence_penalty"]:
            if key in kwargs:
                extra_model_kwargs[key] = kwargs[key]
        if extra_model_kwargs:
            llm_kwargs["model_kwargs"] = extra_model_kwargs

        return ChatDeepSeekInterleaved(**llm_kwargs)

    async def stream(
        self,
        llm,
        messages: List[BaseMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream responses from DeepSeek.

        Properly handles reasoning_content field for thinking mode.
        Includes usage data in the final chunk when available.

        Args:
            llm: ChatDeepSeek instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects with content and thinking
        """
        usage_data = None

        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, 'content') else ""
            thinking = ""

            # DeepSeek returns reasoning_content in additional_kwargs
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
        llm,
        messages: List[BaseMessage],
        **kwargs
    ) -> LLMResponse:
        """
        Invoke DeepSeek and get complete response.

        Args:
            llm: ChatDeepSeek instance
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
        """DeepSeek supports thinking mode."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """
        Get parameters for DeepSeek thinking mode.

        Note: DeepSeek doesn't use effort levels, it's either enabled or disabled.
        """
        return {
            "extra_body": {"thinking": {"type": "enabled"}}
        }

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        DeepSeek doesn't support model listing API.

        Returns pre-defined models.
        """
        return [
            {"id": "deepseek-chat", "name": "DeepSeek Chat"},
            {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner"},
        ]
