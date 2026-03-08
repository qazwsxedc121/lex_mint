"""Adapter for direct local GGUF chat via llama-cpp-python."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from ..base import BaseLLMAdapter
from ..types import LLMResponse, StreamChunk

if TYPE_CHECKING:
    from src.api.services.local_llama_cpp_service import LocalLlamaCppService

LocalLlamaCppService = None


def _get_local_llama_cpp_service_class():
    service_cls = LocalLlamaCppService
    if service_cls is not None:
        return service_cls

    from src.api.services.local_llama_cpp_service import LocalLlamaCppService as imported_service_cls

    return imported_service_cls

logger = logging.getLogger(__name__)
_SENTINEL = object()
_DEFAULT_N_GPU_LAYERS = -1
_THINK_TAG_REGEX = re.compile(r"<think>([\s\S]*?)</think>", re.IGNORECASE)
_TOOL_CALL_REGEX = re.compile(r"<tool_call>\s*([\s\S]*?)\s*</tool_call>", re.IGNORECASE)


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
        disable_thinking: bool = False,
        bound_tools: Optional[List[Dict[str, Any]]] = None,
    ):
        self._service = service
        self.model_id = model_id
        self.model_name = service.model_path.name
        self.profile = {"max_input_tokens": service.n_ctx}
        self._bound_tools = list(bound_tools or [])
        self._defaults = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "top_k": top_k,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "disable_thinking": disable_thinking,
        }

    def _merged_params(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = dict(self._defaults)
        if overrides:
            params.update({k: v for k, v in overrides.items() if v is not None})
        if params.get("max_tokens") is None:
            params["max_tokens"] = 2048
        return params

    def bind_tools(self, _tools: List[Any]):
        return LocalGgufChatModel(
            self._service,
            model_id=self.model_id,
            temperature=float(self._defaults.get("temperature") or 0.7),
            max_tokens=self._defaults.get("max_tokens"),
            top_p=self._defaults.get("top_p"),
            top_k=self._defaults.get("top_k"),
            frequency_penalty=self._defaults.get("frequency_penalty"),
            presence_penalty=self._defaults.get("presence_penalty"),
            disable_thinking=bool(self._defaults.get("disable_thinking", False)),
            bound_tools=[convert_to_openai_tool(tool) for tool in _tools],
        )

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

    @staticmethod
    def _parse_tool_response_content(
        text: str,
        *,
        disable_thinking: bool,
    ) -> tuple[str, str, List[Dict[str, Any]]]:
        raw_text = str(text or "")
        thinking_parts = [match.group(1).strip() for match in _THINK_TAG_REGEX.finditer(raw_text)]
        without_thinking = _THINK_TAG_REGEX.sub("", raw_text)

        tool_calls: List[Dict[str, Any]] = []
        for index, match in enumerate(_TOOL_CALL_REGEX.finditer(without_thinking), start=1):
            payload = match.group(1).strip()
            if not payload:
                continue
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning("Failed to parse local GGUF tool call payload: %s", payload)
                continue
            if not isinstance(parsed, dict):
                continue

            name = str(parsed.get("name") or "").strip()
            args = parsed.get("arguments", parsed.get("args", {}))
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            if not name:
                continue

            tool_calls.append(
                {
                    "name": name,
                    "args": args,
                    "id": str(parsed.get("id") or f"local_gguf_call_{index}"),
                }
            )

        content = _TOOL_CALL_REGEX.sub("", without_thinking).strip()
        thinking = "\n\n".join(part for part in thinking_parts if part)
        if disable_thinking:
            thinking = ""
        return content, thinking, tool_calls

    @staticmethod
    def _build_raw_chunk(
        *,
        content: str,
        thinking: str,
        tool_calls: List[Dict[str, Any]],
    ) -> AIMessageChunk:
        additional_kwargs = {"reasoning_content": thinking} if thinking else {}
        return AIMessageChunk(
            content=content,
            tool_calls=tool_calls,
            additional_kwargs=additional_kwargs,
        )

    @classmethod
    def _complete_with_bound_tools(
        cls,
        llm: LocalGgufChatModel,
        messages: List[BaseMessage],
        params: Dict[str, Any],
    ) -> LLMResponse:
        request_params = dict(params)
        disable_thinking = bool(request_params.pop("disable_thinking", False))
        raw_text = llm._service.complete_messages(
            messages,
            disable_thinking=False,
            tools=list(llm._bound_tools),
            tool_choice="auto",
            **request_params,
        )
        content, thinking, tool_calls = cls._parse_tool_response_content(
            raw_text,
            disable_thinking=disable_thinking,
        )
        raw = cls._build_raw_chunk(content=content, thinking=thinking, tool_calls=tool_calls)
        return LLMResponse(
            content=content,
            thinking=thinking,
            tool_calls=tool_calls,
            raw=raw,
        )

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
        service_cls = _get_local_llama_cpp_service_class()
        raw_n_gpu_layers = kwargs.get("n_gpu_layers", _SENTINEL)
        n_gpu_layers = (
            _DEFAULT_N_GPU_LAYERS
            if raw_n_gpu_layers in {_SENTINEL, None, ""}
            else int(raw_n_gpu_layers)
        )
        service = service_cls(
            model_path=model,
            n_ctx=int(kwargs.get("n_ctx") or 8192),
            n_threads=int(kwargs.get("n_threads") or 0),
            n_gpu_layers=n_gpu_layers,
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
            disable_thinking=bool(kwargs.get("disable_thinking", False)),
        )

    async def stream(
        self,
        llm: LocalGgufChatModel,
        messages: List[BaseMessage],
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        if llm._bound_tools:
            response = await asyncio.to_thread(
                self._complete_with_bound_tools,
                llm,
                messages,
                llm._merged_params(kwargs),
            )
            yield StreamChunk(
                content=response.content,
                thinking=response.thinking,
                tool_calls=response.tool_calls,
                raw=response.raw,
            )
            return
        async for chunk in llm.astream(messages, **kwargs):
            yield StreamChunk(content=str(chunk.content or ""), raw=chunk)

    async def invoke(
        self,
        llm: LocalGgufChatModel,
        messages: List[BaseMessage],
        **kwargs,
    ) -> LLMResponse:
        if llm._bound_tools:
            return await asyncio.to_thread(
                self._complete_with_bound_tools,
                llm,
                messages,
                llm._merged_params(kwargs),
            )
        response = await llm.ainvoke(messages, **kwargs)
        return LLMResponse(
            content=str(response.content or ""),
            thinking=str(getattr(response, "additional_kwargs", {}).get("reasoning_content", "") or ""),
            tool_calls=list(getattr(response, "tool_calls", []) or []),
            raw=response,
        )

    async def fetch_models(
        self,
        base_url: str,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        del base_url, api_key
        from src.api.services.local_llama_cpp_service import discover_local_gguf_models

        return discover_local_gguf_models()

    async def test_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        del base_url, api_key
        from src.api.services.local_llama_cpp_service import discover_local_gguf_models

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
