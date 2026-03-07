"""Native adapter for LM Studio built on the official Python SDK."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
from typing import Any, AsyncIterator, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import lmstudio as lms
from lmstudio import history as lm_history
from lmstudio.json_api import ToolFunctionDef
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool

from ..base import BaseLLMAdapter
from ..model_capability_rules import apply_model_capability_hints
from ..types import LLMResponse, StreamChunk, TokenUsage

logger = logging.getLogger(__name__)

_REASONING_OPTIONS = {"none", "low", "medium", "high"}


class _ThinkTagParser:
    """Incrementally split inline <think> blocks from normal content."""

    _START = "<think>"
    _END = "</think>"

    def __init__(self):
        self._mode = "content"
        self._buffer = ""

    def feed(self, text: str) -> List[Tuple[str, str]]:
        if not text:
            return []
        self._buffer += text
        return self._drain(final=False)

    def finalize(self) -> List[Tuple[str, str]]:
        drained = self._drain(final=True)
        self._mode = "content"
        self._buffer = ""
        return drained

    def _drain(self, *, final: bool) -> List[Tuple[str, str]]:
        output: List[Tuple[str, str]] = []
        while True:
            marker = self._START if self._mode == "content" else self._END
            idx = self._buffer.find(marker)
            if idx >= 0:
                prefix = self._buffer[:idx]
                if prefix:
                    output.append((self._mode, prefix))
                self._buffer = self._buffer[idx + len(marker) :]
                self._mode = "thinking" if self._mode == "content" else "content"
                continue

            if final:
                if self._buffer:
                    output.append((self._mode, self._buffer))
                break

            keep = len(marker) - 1
            if len(self._buffer) <= keep:
                break
            flush = self._buffer[:-keep]
            self._buffer = self._buffer[-keep:]
            if flush:
                output.append((self._mode, flush))
            break
        return output


class LmStudioChatModel:
    """Facade that stores LM Studio model identity and prediction defaults."""

    def __init__(
        self,
        *,
        model: str,
        api_host: str,
        temperature: float,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        context_length: Optional[int] = None,
        reasoning: Optional[str] = None,
    ):
        self.model_name = model
        self.model = model
        self.api_host = api_host
        self.base_url = api_host
        self._defaults = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "top_k": top_k,
            "context_length": context_length,
            "reasoning": reasoning,
        }

    def bind_tools(self, tools: List[Any]):
        return BoundLmStudioChatModel(self, list(tools or []))

    def merged_config(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = dict(self._defaults)
        if overrides:
            params.update({key: value for key, value in overrides.items() if value is not None})

        config: Dict[str, Any] = {}
        if params.get("temperature") is not None:
            config["temperature"] = params["temperature"]
        if params.get("max_tokens") is not None:
            config["max_tokens"] = params["max_tokens"]
        if params.get("top_p") is not None:
            config["top_p_sampling"] = params["top_p"]
        if params.get("top_k") is not None:
            config["top_k_sampling"] = params["top_k"]
        if params.get("context_length") is not None:
            config["context_length"] = params["context_length"]
        if params.get("reasoning") is not None:
            config["reasoning"] = params["reasoning"]
        return config


class BoundLmStudioChatModel:
    """LM Studio chat model with LangChain tools attached."""

    def __init__(self, base: LmStudioChatModel, tools: List[Any]):
        self.base = base
        self.tools = tools
        self.model_name = base.model_name
        self.model = base.model
        self.api_host = base.api_host
        self.base_url = base.base_url

    def bind_tools(self, tools: List[Any]):
        return BoundLmStudioChatModel(self.base, list(tools or []))

    def merged_config(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.base.merged_config(overrides)


class LmStudioAdapter(BaseLLMAdapter):
    """Adapter for LM Studio's official Python SDK."""

    _DEFAULT_TEST_MODEL = ""

    @staticmethod
    def normalize_api_host(base_url: str) -> str:
        candidate = (base_url or "localhost:1234").strip()
        if not candidate:
            return "localhost:1234"
        if "://" not in candidate:
            return candidate.rstrip("/")

        parsed = urlparse(candidate)
        host = parsed.hostname or "localhost"
        port = parsed.port or 1234
        return f"{host}:{port}"

    @staticmethod
    def _resolve_reasoning_value(
        *,
        thinking_enabled: bool,
        reasoning_option: Optional[str],
        reasoning_effort: Optional[str],
        disable_thinking: bool,
    ) -> Optional[str]:
        if disable_thinking:
            return "none"

        candidate = str(reasoning_option or reasoning_effort or "").strip().lower()
        if candidate in _REASONING_OPTIONS:
            return candidate
        if thinking_enabled:
            return "medium"
        return None

    @staticmethod
    def _stats_to_usage(stats: Any) -> Optional[TokenUsage]:
        if stats is None:
            return None

        prompt_tokens = int(getattr(stats, "prompt_tokens_count", 0) or 0)
        completion_tokens = int(getattr(stats, "predicted_tokens_count", 0) or 0)
        total_tokens = int(getattr(stats, "total_tokens_count", 0) or 0)
        if prompt_tokens == 0 and completion_tokens == 0 and total_tokens == 0:
            return None

        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens or (prompt_tokens + completion_tokens),
        )

    @staticmethod
    def _merge_usage(total: Optional[TokenUsage], current: Optional[TokenUsage]) -> Optional[TokenUsage]:
        if current is None:
            return total
        if total is None:
            return current
        reasoning_total = (total.reasoning_tokens or 0) + (current.reasoning_tokens or 0)
        return TokenUsage(
            prompt_tokens=total.prompt_tokens + current.prompt_tokens,
            completion_tokens=total.completion_tokens + current.completion_tokens,
            total_tokens=total.total_tokens + current.total_tokens,
            reasoning_tokens=reasoning_total or None,
        )

    @staticmethod
    def _decode_data_url(data_url: str) -> bytes:
        _, encoded = data_url.split(",", 1)
        return base64.b64decode(encoded)

    @classmethod
    async def _extract_user_parts(
        cls,
        content: Any,
        client: lms.AsyncClient,
    ) -> Tuple[List[str], List[Any]]:
        if isinstance(content, str):
            return [content], []

        text_parts: List[str] = []
        images: List[Any] = []
        if not isinstance(content, list):
            return ["" if content is None else str(content)], []

        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type == "text":
                    text = str(item.get("text") or "")
                    if text:
                        text_parts.append(text)
                    continue
                if item_type == "image_url":
                    image_url = item.get("image_url") or {}
                    data_url = image_url.get("url")
                    if isinstance(data_url, str) and data_url.startswith("data:"):
                        try:
                            image_bytes = cls._decode_data_url(data_url)
                            images.append(await client.prepare_image(image_bytes, name="image"))
                        except Exception as exc:
                            logger.warning("Failed to prepare LM Studio image payload: %s", exc)
                    continue
            elif item is not None:
                text_parts.append(str(item))

        return text_parts, images

    @classmethod
    async def build_history(
        cls,
        messages: Iterable[BaseMessage],
        client: lms.AsyncClient,
    ) -> lm_history.Chat:
        chat = lm_history.Chat()
        for message in messages:
            role = getattr(message, "type", "")
            if role == "system":
                text = "" if message.content is None else str(message.content)
                if text.strip():
                    chat.add_system_prompt(text)
                continue

            if role in {"human", "user"}:
                text_parts, images = await cls._extract_user_parts(message.content, client)
                text_content = "\n".join(part for part in text_parts if part).strip()
                if text_content or images:
                    chat.add_user_message(text_content or " ", images=images)
                continue

            if role == "ai":
                text = "" if message.content is None else str(message.content)
                chat.add_assistant_response(text)
                continue

            if role == "tool":
                text = "" if message.content is None else str(message.content)
                tool_call_id = getattr(message, "tool_call_id", None) or "tool"
                chat.add_tool_result({"toolCallId": str(tool_call_id), "content": text})
                continue

            text = "" if message.content is None else str(message.content)
            if text.strip():
                chat.add_user_message(text)
        return chat

    @staticmethod
    def _tool_parameters_from_langchain(tool: BaseTool) -> Dict[str, Any]:
        args_schema = getattr(tool, "args_schema", None)
        if args_schema is None:
            return {"input": str}

        model_fields = getattr(args_schema, "model_fields", None) or {}
        if not model_fields:
            return {"input": str}

        params: Dict[str, Any] = {}
        for field_name, field_info in model_fields.items():
            annotation = getattr(field_info, "annotation", None) or str
            params[field_name] = annotation
        return params

    @classmethod
    def _sdk_tool_from_langchain(cls, tool: BaseTool) -> ToolFunctionDef:
        async def _invoke_tool(**kwargs):
            return await tool.ainvoke(kwargs)

        return ToolFunctionDef(
            name=tool.name,
            description=(tool.description or tool.name or "tool").strip(),
            parameters=cls._tool_parameters_from_langchain(tool),
            implementation=_invoke_tool,
        )

    @classmethod
    def _normalize_sdk_tools(cls, tools: List[Any]) -> List[Any]:
        normalized: List[Any] = []
        for tool in tools:
            if isinstance(tool, ToolFunctionDef):
                normalized.append(tool)
            elif isinstance(tool, BaseTool):
                normalized.append(cls._sdk_tool_from_langchain(tool))
            else:
                normalized.append(tool)
        return normalized

    @staticmethod
    def _collect_parser_output(
        parser: _ThinkTagParser,
        text: str,
        emit: Callable[[str, str], None],
        *,
        force_thinking: bool = False,
    ) -> None:
        if not text:
            return
        if force_thinking:
            emit("thinking", text)
            return
        for kind, chunk in parser.feed(text):
            emit(kind, chunk)

    @staticmethod
    def _parse_text_with_think_tags(text: str) -> Tuple[str, str]:
        parser = _ThinkTagParser()
        content_parts: List[str] = []
        thinking_parts: List[str] = []
        for kind, chunk in parser.feed(text or "") + parser.finalize():
            if kind == "thinking":
                thinking_parts.append(chunk)
            else:
                content_parts.append(chunk)
        return "".join(content_parts), "".join(thinking_parts)

    @staticmethod
    def _parse_model_metadata(info: Any) -> Dict[str, Any]:
        model_id = str(getattr(info, "model_key", "") or "")
        has_vision = bool(getattr(info, "vision", False))
        has_function_calling = bool(getattr(info, "trained_for_tool_use", False))
        context_length = int(getattr(info, "max_context_length", 0) or 4096)

        capabilities: Dict[str, Any] = {
            "context_length": context_length,
            "vision": has_vision,
            "function_calling": has_function_calling,
            "reasoning": True,
            "streaming": True,
            "file_upload": has_vision,
            "image_output": False,
            "reasoning_controls": {
                "mode": "enum",
                "param": "reasoning",
                "options": ["none", "low", "medium", "high"],
                "default_option": "medium",
                "disable_supported": True,
            },
        }
        capabilities = apply_model_capability_hints(model_id, capabilities, provider_id="lmstudio")

        tags: List[str] = []
        if capabilities.get("vision"):
            tags.append("vision")
        if capabilities.get("function_calling"):
            tags.append("function-calling")
        if capabilities.get("reasoning"):
            tags.append("reasoning")
        if not tags:
            tags.append("chat")

        return {"capabilities": capabilities, "tags": tags}

    async def _open_model(self, llm: LmStudioChatModel) -> tuple[lms.AsyncClient, Any]:
        client = lms.AsyncClient(llm.api_host)
        await client.__aenter__()
        try:
            model = await client.llm.model(llm.model)
            return client, model
        except Exception:
            await client.__aexit__(None, None, None)
            raise

    async def _stream_with_tools(
        self,
        llm: BoundLmStudioChatModel,
        messages: List[BaseMessage],
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        client, model = await self._open_model(llm.base)
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        parser = _ThinkTagParser()
        emitted_content = False
        final_content = ""
        total_usage: Optional[TokenUsage] = None

        def emit(kind: str, chunk: str) -> None:
            if chunk:
                queue.put_nowait((kind, chunk))

        def on_prediction_fragment(fragment: Any, _round_index: int) -> None:
            text = str(getattr(fragment, "content", "") or "")
            reasoning_type = str(getattr(fragment, "reasoning_type", "none") or "none")
            self._collect_parser_output(parser, text, emit, force_thinking=(reasoning_type != "none"))

        def on_prediction_completed(round_result: Any) -> None:
            nonlocal final_content, total_usage
            final_content = str(getattr(round_result, "content", "") or final_content)
            total_usage = self._merge_usage(
                total_usage,
                self._stats_to_usage(getattr(round_result, "stats", None)),
            )
            for kind, chunk in parser.finalize():
                emit(kind, chunk)

        async def _run_act() -> None:
            history = await self.build_history(messages, client)
            await model.act(
                history,
                self._normalize_sdk_tools(llm.tools),
                max_prediction_rounds=3,
                config=llm.merged_config(kwargs),
                on_prediction_fragment=on_prediction_fragment,
                on_prediction_completed=on_prediction_completed,
            )

        task = asyncio.create_task(_run_act())
        try:
            while True:
                if task.done() and queue.empty():
                    break
                try:
                    kind, payload = await asyncio.wait_for(queue.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    continue
                if kind == "content":
                    emitted_content = True
                    yield StreamChunk(content=payload, raw=payload)
                else:
                    yield StreamChunk(content="", thinking=payload, raw=payload)

            await task
            if final_content and not emitted_content:
                content, thinking = self._parse_text_with_think_tags(final_content)
                if thinking:
                    yield StreamChunk(content="", thinking=thinking, raw=final_content)
                if content:
                    yield StreamChunk(content=content, raw=final_content)
            if total_usage is not None:
                yield StreamChunk(content="", usage=total_usage, raw=total_usage)
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(Exception):
                    await task
            await client.__aexit__(None, None, None)

    async def _invoke_with_tools(
        self,
        llm: BoundLmStudioChatModel,
        messages: List[BaseMessage],
        **kwargs,
    ) -> LLMResponse:
        client, model = await self._open_model(llm.base)
        total_usage: Optional[TokenUsage] = None
        final_content = ""
        try:
            history = await self.build_history(messages, client)

            def on_prediction_completed(round_result: Any) -> None:
                nonlocal total_usage, final_content
                final_content = str(getattr(round_result, "content", "") or final_content)
                total_usage = self._merge_usage(
                    total_usage,
                    self._stats_to_usage(getattr(round_result, "stats", None)),
                )

            await model.act(
                history,
                self._normalize_sdk_tools(llm.tools),
                max_prediction_rounds=3,
                config=llm.merged_config(kwargs),
                on_prediction_completed=on_prediction_completed,
            )
            content, thinking = self._parse_text_with_think_tags(final_content)
            return LLMResponse(
                content=content or final_content,
                thinking=thinking,
                usage=total_usage,
                raw=final_content,
            )
        finally:
            await client.__aexit__(None, None, None)

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        **kwargs,
    ) -> LmStudioChatModel:
        del api_key, streaming
        reasoning = self._resolve_reasoning_value(
            thinking_enabled=thinking_enabled,
            reasoning_option=kwargs.get("reasoning_option"),
            reasoning_effort=kwargs.get("reasoning_effort"),
            disable_thinking=bool(kwargs.get("disable_thinking", False)),
        )
        context_length = kwargs.get("context_length") or kwargs.get("num_ctx")
        return LmStudioChatModel(
            model=model,
            api_host=self.normalize_api_host(base_url),
            temperature=temperature,
            max_tokens=kwargs.get("max_tokens"),
            top_p=kwargs.get("top_p"),
            top_k=kwargs.get("top_k"),
            context_length=context_length,
            reasoning=reasoning,
        )

    async def stream(
        self,
        llm: LmStudioChatModel | BoundLmStudioChatModel,
        messages: List[BaseMessage],
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        if isinstance(llm, BoundLmStudioChatModel):
            async for chunk in self._stream_with_tools(llm, messages, **kwargs):
                yield chunk
            return

        client, model = await self._open_model(llm)
        try:
            history = await self.build_history(messages, client)
            parser = _ThinkTagParser()
            stream = await model.respond_stream(history, config=llm.merged_config(kwargs))
            async with stream as active_stream:
                async for fragment in active_stream:
                    text = str(getattr(fragment, "content", "") or "")
                    reasoning_type = str(getattr(fragment, "reasoning_type", "none") or "none")
                    if reasoning_type != "none":
                        yield StreamChunk(content="", thinking=text, raw=fragment)
                        continue
                    for kind, chunk in parser.feed(text):
                        if kind == "thinking":
                            yield StreamChunk(content="", thinking=chunk, raw=fragment)
                        else:
                            yield StreamChunk(content=chunk, raw=fragment)

                for kind, chunk in parser.finalize():
                    if kind == "thinking":
                        yield StreamChunk(content="", thinking=chunk, raw=active_stream)
                    else:
                        yield StreamChunk(content=chunk, raw=active_stream)

                result = active_stream.result()
                usage = self._stats_to_usage(getattr(result, "stats", None))
                if usage is not None:
                    yield StreamChunk(content="", usage=usage, raw=result)
        finally:
            await client.__aexit__(None, None, None)

    async def invoke(
        self,
        llm: LmStudioChatModel | BoundLmStudioChatModel,
        messages: List[BaseMessage],
        **kwargs,
    ) -> LLMResponse:
        if isinstance(llm, BoundLmStudioChatModel):
            return await self._invoke_with_tools(llm, messages, **kwargs)

        client, model = await self._open_model(llm)
        try:
            history = await self.build_history(messages, client)
            result = await model.respond(history, config=llm.merged_config(kwargs))
            usage = self._stats_to_usage(getattr(result, "stats", None))
            content, thinking = self._parse_text_with_think_tags(str(getattr(result, "content", "") or ""))
            return LLMResponse(
                content=content or str(getattr(result, "content", "") or ""),
                thinking=thinking,
                usage=usage,
                raw=result,
            )
        finally:
            await client.__aexit__(None, None, None)

    def supports_thinking(self) -> bool:
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        option = effort if effort in _REASONING_OPTIONS else "medium"
        return {"reasoning": option}

    async def fetch_models(self, base_url: str, api_key: str) -> List[Dict[str, Any]]:
        del api_key
        try:
            async with lms.AsyncClient(self.normalize_api_host(base_url)) as client:
                downloaded = await client.llm.list_downloaded()
                loaded = await client.llm.list_loaded()

            loaded_ids = {str(getattr(model, "identifier", "") or "") for model in loaded}
            models: List[Dict[str, Any]] = []
            for item in downloaded:
                info = getattr(item, "info", None)
                if info is None:
                    continue
                model_id = str(getattr(info, "model_key", "") or "")
                if not model_id:
                    continue

                entry: Dict[str, Any] = {
                    "id": model_id,
                    "name": str(getattr(info, "display_name", None) or model_id),
                }
                entry.update(self._parse_model_metadata(info))
                if model_id in loaded_ids:
                    entry.setdefault("tags", []).append("loaded")
                models.append(entry)

            return sorted(models, key=lambda item: item["id"])
        except Exception as exc:
            logger.warning("Failed to fetch LM Studio models via SDK: %s", exc)
            return []

    async def test_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        del api_key
        try:
            async with lms.AsyncClient(self.normalize_api_host(base_url)) as client:
                downloaded = await client.llm.list_downloaded()
                loaded = await client.llm.list_loaded()

            downloaded_ids = {
                str(getattr(getattr(item, "info", None), "model_key", "") or "")
                for item in downloaded
                if getattr(item, "info", None) is not None
            }
            loaded_ids = {str(getattr(item, "identifier", "") or "") for item in loaded}

            if model_id and model_id not in downloaded_ids and model_id not in loaded_ids:
                return False, f"Connected to LM Studio, but model '{model_id}' is not installed"
            if not downloaded_ids and not loaded_ids:
                return True, "Connected to LM Studio, but no models are installed"

            return True, f"Connected to LM Studio with {len(downloaded_ids or loaded_ids)} available model(s)"
        except Exception as exc:
            return False, f"Cannot connect to LM Studio via SDK: {exc}"
