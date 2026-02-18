"""
ChatOpenAI subclass with reasoning_content support.

Many OpenAI-compatible providers (Zhipu GLM, Volcano Engine Doubao, etc.)
return chain-of-thought reasoning in a `reasoning_content` field alongside
the standard `content` field.  LangChain's built-in ChatOpenAI silently
discards this non-standard field.

ChatReasoningOpenAI extends BaseChatOpenAI to extract `reasoning_content`
from both streaming and non-streaming responses and place it into
`additional_kwargs["reasoning_content"]` so that downstream code can
access it through the normal LangChain message interface.

The implementation mirrors `langchain-deepseek`'s ChatDeepSeek, which
uses the identical technique for DeepSeek's reasoning_content.
"""
from __future__ import annotations

from typing import Any

import openai
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai.chat_models.base import BaseChatOpenAI


class ChatReasoningOpenAI(BaseChatOpenAI):
    """ChatOpenAI variant that surfaces `reasoning_content` from the API."""

    def _create_chat_result(
        self,
        response: dict | openai.BaseModel,
        generation_info: dict | None = None,
    ) -> ChatResult:
        """Non-streaming: extract reasoning_content from the full response."""
        result = super()._create_chat_result(response, generation_info)

        if not isinstance(response, openai.BaseModel):
            return result

        choices = getattr(response, "choices", None)
        if not choices:
            return result

        msg = choices[0].message

        # Primary: direct reasoning_content attribute
        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            result.generations[0].message.additional_kwargs[
                "reasoning_content"
            ] = msg.reasoning_content

        # Fallback: model_extra dict (e.g. via OpenRouter)
        elif hasattr(msg, "model_extra") and isinstance(msg.model_extra, dict):
            reasoning = msg.model_extra.get("reasoning_content") or msg.model_extra.get("reasoning")
            if reasoning:
                result.generations[0].message.additional_kwargs[
                    "reasoning_content"
                ] = reasoning

        return result

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        """Streaming: extract reasoning_content from each SSE chunk."""
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )

        if not generation_chunk:
            return generation_chunk

        choices = chunk.get("choices")
        if not choices:
            return generation_chunk

        delta = choices[0].get("delta", {})

        if isinstance(generation_chunk.message, AIMessageChunk):
            # Primary: reasoning_content in delta
            reasoning_content = delta.get("reasoning_content")
            if reasoning_content is not None:
                generation_chunk.message.additional_kwargs[
                    "reasoning_content"
                ] = reasoning_content
            else:
                # Fallback: "reasoning" key (some proxies)
                reasoning = delta.get("reasoning")
                if reasoning is not None:
                    generation_chunk.message.additional_kwargs[
                        "reasoning_content"
                    ] = reasoning

        return generation_chunk
