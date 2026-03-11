"""Local llama-cpp service for GGUF text generation and chat."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from typing import Any, Iterable, Iterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.core.paths import (
    appdata_models_root,
    configured_models_root,
    install_models_root,
    resolve_model_path,
)
from src.providers.model_capability_rules import apply_model_capability_hints

logger = logging.getLogger(__name__)

_DEFAULT_DISCOVERY_CAPABILITIES = {
    "context_length": 8192,
    "vision": False,
    "function_calling": False,
    "reasoning": False,
    "requires_interleaved_thinking": False,
    "streaming": True,
    "file_upload": False,
    "image_output": False,
}


def local_llm_models_dir() -> Path:
    """Return the discoverable local GGUF model directory under the install/source root."""
    return install_models_root() / "llm"


def _discovery_model_roots() -> list[Path]:
    """Return GGUF discovery roots in priority order."""
    roots: list[Path] = []
    configured_root = configured_models_root()
    if configured_root is not None:
        roots.append(configured_root)
    roots.append(appdata_models_root())
    roots.append(install_models_root())

    unique_roots: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        normalized = str(root.resolve())
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_roots.append(root)
    return unique_roots


def discover_local_gguf_models() -> list[dict[str, Any]]:
    """Discover GGUF files available for direct local chat."""
    discovered_by_id: dict[str, dict[str, Any]] = {}

    for models_root in _discovery_model_roots():
        llm_root = models_root / "llm"
        if not llm_root.exists():
            continue

        for model_path in sorted(llm_root.rglob("*.gguf")):
            if not model_path.is_file():
                continue
            relative_model_path = model_path.relative_to(models_root).as_posix()
            if relative_model_path in discovered_by_id:
                continue
            stem = model_path.stem
            tags = ["local", "gguf", "chat"]
            if "reason" in stem.lower():
                tags.append("reasoning")
            discovered_by_id[relative_model_path] = {
                "id": relative_model_path,
                "name": stem,
                "tags": tags,
                "capabilities": apply_model_capability_hints(
                    relative_model_path,
                    None,
                    provider_defaults=dict(_DEFAULT_DISCOVERY_CAPABILITIES),
                    provider_id="local_gguf",
                ) or dict(_DEFAULT_DISCOVERY_CAPABILITIES),
            }

    return list(discovered_by_id.values())


class LocalLlamaCppService:
    """GGUF text generation wrapper based on llama-cpp-python."""

    _cache_lock = Lock()
    _model_cache: dict[tuple[str, int, int, int], Any] = {}
    _inference_locks: dict[tuple[str, int, int, int], Lock] = {}

    def __init__(
        self,
        model_path: str,
        *,
        n_ctx: int = 8192,
        n_threads: int = 0,
        n_gpu_layers: int = 0,
    ):
        self.model_path = self._resolve_model_path(model_path)
        self.n_ctx = max(512, int(n_ctx or 8192))
        self.n_threads = max(0, int(n_threads or 0))
        self.n_gpu_layers = max(-1, int(n_gpu_layers if n_gpu_layers is not None else 0))

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Local GGUF LLM model not found: {self.model_path}. "
                f"Please copy your .gguf file to this path or update settings."
            )

    @staticmethod
    def _resolve_model_path(model_path: str) -> Path:
        resolved = resolve_model_path(model_path)
        logger.info("Resolved local GGUF model path: %s -> %s", model_path, resolved)
        return resolved

    def _cache_key(self) -> tuple[str, int, int, int]:
        return (
            str(self.model_path.resolve()),
            self.n_ctx,
            self.n_threads,
            self.n_gpu_layers,
        )

    def _get_inference_lock(self) -> Lock:
        cache_key = self._cache_key()
        with self._cache_lock:
            lock = self._inference_locks.get(cache_key)
            if lock is None:
                lock = Lock()
                self._inference_locks[cache_key] = lock
            return lock

    def _get_model(self):
        cache_key = self._cache_key()

        with self._cache_lock:
            cached = self._model_cache.get(cache_key)
            if cached is not None:
                return cached

            from llama_cpp import Llama

            kwargs = {
                "model_path": str(self.model_path),
                "n_ctx": self.n_ctx,
                "verbose": False,
            }
            if self.n_threads > 0:
                kwargs["n_threads"] = self.n_threads
            if self.n_gpu_layers != 0:
                kwargs["n_gpu_layers"] = self.n_gpu_layers

            model = Llama(**kwargs)
            self._model_cache[cache_key] = model
            return model

    @staticmethod
    def _extract_text_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    text_value = item.get("text")
                    if isinstance(text_value, str) and text_value:
                        text_parts.append(text_value)
            return "\n".join(text_parts)
        return str(content or "")

    @classmethod
    def _normalize_messages(cls, messages: Iterable[BaseMessage | dict[str, Any]]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for message in messages:
            if isinstance(message, dict):
                role = str(message.get("role") or "user").strip().lower() or "user"
                content = cls._extract_text_content(message.get("content"))
            elif isinstance(message, SystemMessage):
                role = "system"
                content = cls._extract_text_content(message.content)
            elif isinstance(message, HumanMessage):
                role = "user"
                content = cls._extract_text_content(message.content)
            elif isinstance(message, AIMessage):
                role = "assistant"
                content = cls._extract_text_content(message.content)
            elif isinstance(message, BaseMessage):
                role = str(getattr(message, "type", "user") or "user").strip().lower() or "user"
                content = cls._extract_text_content(getattr(message, "content", ""))
            else:
                continue

            if role not in {"system", "user", "assistant"}:
                role = "assistant" if role == "ai" else "user"

            normalized.append({"role": role, "content": content})
        return normalized

    @staticmethod
    def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
        prompt_parts: list[str] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            else:
                prompt_parts.append(f"User: {content}")
        prompt_parts.append("Assistant:")
        return "\n\n".join(prompt_parts)

    @staticmethod
    def _build_generation_kwargs(
        *,
        temperature: float,
        max_tokens: int,
        top_p: float | None = None,
        top_k: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "temperature": max(0.0, min(2.0, float(temperature))),
            "max_tokens": max(1, int(max_tokens or 2048)),
        }
        if top_p is not None:
            kwargs["top_p"] = max(0.0, min(1.0, float(top_p)))
        if top_k is not None:
            kwargs["top_k"] = max(1, int(top_k))
        if frequency_penalty is not None:
            kwargs["frequency_penalty"] = float(frequency_penalty)
        if presence_penalty is not None:
            kwargs["presence_penalty"] = float(presence_penalty)
        return kwargs

    def _stream_chat_messages(
        self,
        messages: list[dict[str, str]],
        *,
        generation_kwargs: dict[str, Any],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> Iterator[str]:
        model = self._get_model()
        with self._get_inference_lock():
            request_kwargs: dict[str, Any] = {
                "messages": messages,
                "stream": True,
                **generation_kwargs,
            }
            if tools:
                request_kwargs["tools"] = tools
                request_kwargs["tool_choice"] = tool_choice or "auto"
            stream = model.create_chat_completion(**request_kwargs)
            for chunk in stream:
                if not isinstance(chunk, dict):
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content

    def _stream_text_completion(
        self,
        prompt: str,
        *,
        generation_kwargs: dict[str, Any],
    ) -> Iterator[str]:
        model = self._get_model()
        with self._get_inference_lock():
            stream = model.create_completion(
                prompt=prompt,
                stream=True,
                **generation_kwargs,
            )
            for chunk in stream:
                if not isinstance(chunk, dict):
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                text = choices[0].get("text")
                if text:
                    yield text

    @staticmethod
    def _filter_thinking_tokens(chunks: Iterable[str]) -> Iterator[str]:
        open_tag = "<think>"
        close_tag = "</think>"
        in_thinking = False
        buffer = ""

        def _prefix_overlap(text: str, token: str) -> int:
            max_len = min(len(text), len(token) - 1)
            for size in range(max_len, 0, -1):
                if text.endswith(token[:size]):
                    return size
            return 0

        for chunk in chunks:
            if not chunk:
                continue
            buffer += str(chunk)

            while buffer:
                if in_thinking:
                    close_idx = buffer.find(close_tag)
                    if close_idx == -1:
                        keep = _prefix_overlap(buffer, close_tag)
                        buffer = buffer[-keep:] if keep else ""
                        break
                    buffer = buffer[close_idx + len(close_tag):]
                    in_thinking = False
                    continue

                open_idx = buffer.find(open_tag)
                if open_idx != -1:
                    visible = buffer[:open_idx]
                    if visible:
                        yield visible
                    buffer = buffer[open_idx + len(open_tag):]
                    in_thinking = True
                    continue

                keep = _prefix_overlap(buffer, open_tag)
                if len(buffer) > keep:
                    yield buffer[:-keep] if keep else buffer
                buffer = buffer[-keep:] if keep else ""
                break

        if not in_thinking and buffer:
            yield buffer

    def stream_messages(
        self,
        messages: Iterable[BaseMessage | dict[str, Any]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        top_p: float | None = None,
        top_k: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        disable_thinking: bool = False,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> Iterator[str]:
        """Stream completion tokens for a chat message sequence."""
        normalized_messages = self._normalize_messages(messages)
        if not normalized_messages:
            normalized_messages = [{"role": "user", "content": ""}]
        generation_kwargs = self._build_generation_kwargs(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
        )

        try:
            stream = self._stream_chat_messages(
                normalized_messages,
                generation_kwargs=generation_kwargs,
                tools=tools,
                tool_choice=tool_choice,
            )
            yield from self._filter_thinking_tokens(stream) if disable_thinking else stream
            return
        except Exception as e:
            if tools:
                raise
            logger.info("chat_completion failed, fallback to completion: %s", e)

        fallback_stream = self._stream_text_completion(
            self._messages_to_prompt(normalized_messages),
            generation_kwargs=generation_kwargs,
        )
        yield from self._filter_thinking_tokens(fallback_stream) if disable_thinking else fallback_stream

    def complete_messages(
        self,
        messages: Iterable[BaseMessage | dict[str, Any]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        top_p: float | None = None,
        top_k: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        disable_thinking: bool = False,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> str:
        """Generate full completion text for a chat message sequence."""
        return "".join(
            self.stream_messages(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                top_k=top_k,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                disable_thinking=disable_thinking,
                tools=tools,
                tool_choice=tool_choice,
            )
        )

    def stream_prompt(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        """Stream completion tokens for a single user prompt."""
        yield from self.stream_messages(
            [{"role": "user", "content": prompt or ""}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def complete_prompt(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Generate full completion text for a single user prompt."""
        return self.complete_messages(
            [{"role": "user", "content": prompt or ""}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
