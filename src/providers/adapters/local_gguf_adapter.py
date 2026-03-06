"""Adapter for direct local GGUF chat via llama-cpp-python."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

from src.api.services.local_llama_cpp_service import (
    LocalLlamaCppService,
    discover_local_gguf_models,
)

from ..base import BaseLLMAdapter
from ..types import LLMResponse, StreamChunk

logger = logging.getLogger(__name__)
_SENTINEL = object()


class LocalGgufChatModel:
    """Minimal chat-model facade for local GGUF inference."""

    def __init__(
        self,
        service: LocalLlamaCppService,
        *,
        model_id: str,
        temperature: float,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ):
        self._service = service
        self.model_id = model_id
        self.model_name = service.model_path.name
        self.profile = {"max_input_tokens": service.n_ctx}
        self._defaults = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "top_k": top_k,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
        }

    def _merged_params(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = dict(self._defaults)
        if overrides:
            params.update({k: v for k, v in overrides.items() if v is not None})
        if params.get("max_tokens") is None:
            params["max_tokens"] = 2048
        return params

    def bind_tools(self, _tools: List[Any]):
        raise NotImplementedError("Tool calling is not supported for local GGUF models")

    def invoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        content = self._service.complete_messages(messages, **self._merged_params(kwargs))
        return AIMessage(content=content)

    async def ainvoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        return await asyncio.to_thread(self.invoke, messages, **kwargs)

    async def astream(self, messages: List[BaseMessage], **kwargs) -> AsyncIterator[AIMessageChunk]:
        iterator = self._service.stream_messages(messages, **self._merged_params(kwargs))
        while True:
            token = await asyncio.to_thread(next, iterator, _SENTINEL)
            if token is _SENTINEL:
                break
            yield AIMessageChunk(content=str(token))


class LocalGgufAdapter(BaseLLMAdapter):
    """Adapter for direct local GGUF chat inference."""

    _DEFAULT_TEST_MODEL = ""

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        **kwargs,
    ) -> LocalGgufChatModel:
        del base_url, api_key, streaming, thinking_enabled
        service = LocalLlamaCppService(
            model_path=model,
            n_ctx=int(kwargs.get("n_ctx") or 8192),
            n_threads=int(kwargs.get("n_threads") or 0),
            n_gpu_layers=int(kwargs.get("n_gpu_layers") or 0),
        )
        return LocalGgufChatModel(
            service,
            model_id=model,
            temperature=temperature,
            max_tokens=kwargs.get("max_tokens"),
            top_p=kwargs.get("top_p"),
            top_k=kwargs.get("top_k"),
            frequency_penalty=kwargs.get("frequency_penalty"),
            presence_penalty=kwargs.get("presence_penalty"),
        )

    async def stream(
        self,
        llm: LocalGgufChatModel,
        messages: List[BaseMessage],
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        async for chunk in llm.astream(messages, **kwargs):
            yield StreamChunk(content=str(chunk.content or ""), raw=chunk)

    async def invoke(
        self,
        llm: LocalGgufChatModel,
        messages: List[BaseMessage],
        **kwargs,
    ) -> LLMResponse:
        response = await llm.ainvoke(messages, **kwargs)
        return LLMResponse(content=str(response.content or ""), raw=response)

    async def fetch_models(
        self,
        base_url: str,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        del base_url, api_key
        return discover_local_gguf_models()

    async def test_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        del base_url, api_key
        selected_model_id = model_id
        if not selected_model_id:
            models = discover_local_gguf_models()
            if not models:
                return False, "No GGUF models found under models/llm"
            selected_model_id = str(models[0]["id"])

        try:
            llm = self.create_llm(
                model=selected_model_id,
                base_url="local://gguf",
                api_key="",
                temperature=0.0,
                streaming=False,
                max_tokens=16,
            )
            response = await self.invoke(llm, [])
            if response.content:
                return True, f"Loaded local GGUF model '{selected_model_id}'"
            return False, f"Model '{selected_model_id}' returned an empty response"
        except FileNotFoundError as exc:
            return False, str(exc)
        except Exception as exc:
            logger.warning("Local GGUF test connection failed: %s", exc)
            return False, f"Failed to load local GGUF model '{selected_model_id}': {exc}"
