"""Local llama-cpp service for GGUF text generation."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from typing import Any, Iterator

from ..paths import repo_root

logger = logging.getLogger(__name__)


class LocalLlamaCppService:
    """GGUF text generation wrapper based on llama-cpp-python."""

    _cache_lock = Lock()
    _model_cache: dict[tuple[str, int, int, int], Any] = {}

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
        self.n_gpu_layers = max(0, int(n_gpu_layers or 0))

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Local GGUF LLM model not found: {self.model_path}. "
                f"Please copy your .gguf file to this path or update settings."
            )

    @staticmethod
    def _resolve_model_path(model_path: str) -> Path:
        candidate = Path(model_path).expanduser()
        if not candidate.is_absolute():
            candidate = repo_root() / candidate
        return candidate

    def _get_model(self):
        cache_key = (
            str(self.model_path.resolve()),
            self.n_ctx,
            self.n_threads,
            self.n_gpu_layers,
        )

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
            if self.n_gpu_layers > 0:
                kwargs["n_gpu_layers"] = self.n_gpu_layers

            model = Llama(**kwargs)
            self._model_cache[cache_key] = model
            return model

    def _stream_chat_completion(
        self,
        prompt: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> Iterator[str]:
        model = self._get_model()
        stream = model.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
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
        temperature: float,
        max_tokens: int,
    ) -> Iterator[str]:
        model = self._get_model()
        stream = model.create_completion(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            choices = chunk.get("choices") or []
            if not choices:
                continue
            text = choices[0].get("text")
            if text:
                yield text

    def stream_prompt(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        """Stream completion tokens for a prompt."""
        safe_temp = max(0.0, min(2.0, float(temperature)))
        safe_max_tokens = max(1, int(max_tokens or 2048))
        text = prompt or ""

        try:
            yield from self._stream_chat_completion(
                text,
                temperature=safe_temp,
                max_tokens=safe_max_tokens,
            )
            return
        except Exception as e:
            logger.info(f"chat_completion failed, fallback to completion: {e}")

        yield from self._stream_text_completion(
            text,
            temperature=safe_temp,
            max_tokens=safe_max_tokens,
        )

    def complete_prompt(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Generate full completion text for a prompt."""
        return "".join(
            self.stream_prompt(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
