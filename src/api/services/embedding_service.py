"""
Embedding Service

Provides abstraction over API-based and local embedding models.
Uses LangChain Embeddings interface.
"""
import logging
import math
from threading import Lock
import yaml
from pathlib import Path
from typing import Any, Optional

from .rag_config_service import RagConfigService
from .model_config_service import ModelConfigService
from ..paths import repo_root

logger = logging.getLogger(__name__)


class LlamaCppEmbeddings:
    """Embeddings wrapper backed by llama-cpp-python (GGUF)."""

    _cache_lock = Lock()
    _model_cache: dict[tuple[str, int, int, int], Any] = {}

    def __init__(
        self,
        model_path: str,
        *,
        n_ctx: int = 2048,
        n_threads: int = 0,
        n_gpu_layers: int = 0,
        normalize: bool = True,
    ):
        self.model_path = self._resolve_model_path(model_path)
        self.n_ctx = max(256, int(n_ctx or 2048))
        self.n_threads = max(0, int(n_threads or 0))
        self.n_gpu_layers = int(n_gpu_layers or 0)
        self.normalize = bool(normalize)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"GGUF embedding model not found: {self.model_path}. "
                f"Please copy your .gguf file to this path or update RAG settings."
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
                "embedding": True,
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

    @staticmethod
    def _extract_vectors(raw: Any) -> list[list[float]]:
        if raw is None:
            raise ValueError("No embedding returned from llama-cpp.")

        if isinstance(raw, dict):
            if isinstance(raw.get("data"), list):
                vectors: list[list[float]] = []
                for item in raw["data"]:
                    if isinstance(item, dict) and isinstance(item.get("embedding"), list):
                        vectors.append([float(x) for x in item["embedding"]])
                if vectors:
                    return vectors

            if isinstance(raw.get("embedding"), list):
                return [[float(x) for x in raw["embedding"]]]

            if isinstance(raw.get("embeddings"), list):
                embs = raw["embeddings"]
                if embs and isinstance(embs[0], list):
                    return [[float(x) for x in emb] for emb in embs]

        if isinstance(raw, list):
            if raw and isinstance(raw[0], list):
                return [[float(x) for x in emb] for emb in raw]
            if not raw or isinstance(raw[0], (float, int)):
                return [[float(x) for x in raw]]

        raise ValueError(f"Unsupported embedding response format: {type(raw).__name__}")

    @staticmethod
    def _l2_normalize(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(x * x for x in vector))
        if norm <= 0:
            return vector
        return [x / norm for x in vector]

    def _embed_single(self, text: str) -> list[float]:
        model = self._get_model()
        payload = text or ""

        if hasattr(model, "embed"):
            raw = model.embed(payload)
        else:
            raw = model.create_embedding(payload)

        vector = self._extract_vectors(raw)[0]
        if self.normalize:
            return self._l2_normalize(vector)
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._get_model()
        payloads = [text or "" for text in texts]

        try:
            if hasattr(model, "embed"):
                raw = model.embed(payloads)
            else:
                raw = model.create_embedding(payloads)
            vectors = self._extract_vectors(raw)
            if len(vectors) != len(payloads):
                raise ValueError("Embedding count mismatch.")
            if self.normalize:
                return [self._l2_normalize(v) for v in vectors]
            return vectors
        except Exception:
            return [self._embed_single(text) for text in payloads]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_single(text or "")


class EmbeddingService:
    """Service for creating embedding functions based on RAG config"""

    def __init__(self):
        self.rag_config_service = RagConfigService()
        self.model_config_service = ModelConfigService()

    def get_embedding_function(self, override_model: Optional[str] = None):
        """
        Get the appropriate embedding function based on config.

        Args:
            override_model: Optional model override (plain model name or provider:model format)

        Returns:
            LangChain Embeddings instance
        """
        config = self.rag_config_service.config.embedding

        if config.provider == "local":
            return self._get_local_embeddings(config.local_model, config.local_device)
        if config.provider == "local_gguf":
            return self._get_local_gguf_embeddings(
                model_path=config.local_gguf_model_path,
                n_ctx=config.local_gguf_n_ctx,
                n_threads=config.local_gguf_n_threads,
                n_gpu_layers=config.local_gguf_n_gpu_layers,
                normalize=config.local_gguf_normalize,
            )
        else:
            model = override_model or config.api_model
            return self._get_api_embeddings(model, config.api_base_url, config.api_key, config.batch_size)

    def _get_provider_base_url_sync(self, provider_id: str) -> Optional[str]:
        """Read provider base_url directly from models_config.yaml (sync)"""
        try:
            config_path = self.model_config_service.config_path
            if not config_path.exists():
                return None
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            for provider in data.get('providers', []):
                if provider.get('id') == provider_id:
                    return provider.get('base_url')
        except Exception as e:
            logger.warning(f"Failed to read provider base_url for {provider_id}: {e}")
        return None

    def _get_api_embeddings(
        self,
        model_id: str,
        config_base_url: str = "",
        config_api_key: str = "",
        batch_size: Optional[int] = None,
    ):
        """
        Get API-based embeddings using OpenAI-compatible endpoint.

        Resolution order for base_url and api_key:
        1. RAG config's dedicated api_base_url / api_key (if set)
        2. Fall back to LLM provider config (using provider:model format)

        Args:
            model_id: Model name, or provider:model format for fallback to LLM provider
            config_base_url: Base URL from RAG config (takes priority)
            config_api_key: API key from RAG config (takes priority)
        """
        from langchain_openai import OpenAIEmbeddings

        # If RAG config has a dedicated base_url, use it directly.
        # API key is optional for local OpenAI-compatible endpoints.
        if config_base_url:
            # model_id may contain provider: prefix, strip it
            model_name = model_id.split(":", 1)[-1] if ":" in model_id else model_id
            return OpenAIEmbeddings(
                model=model_name,
                api_key=config_api_key or "local",
                base_url=config_base_url,
                check_embedding_ctx_length=False,
                chunk_size=batch_size,
            )

        # Fall back: resolve from LLM provider config using provider:model format
        parts = model_id.split(":", 1)
        if len(parts) == 2:
            provider_id, model_name = parts
        else:
            provider_id = "deepseek"
            model_name = model_id

        # Try RAG config api_key first, then fall back to provider api_key
        api_key = config_api_key if config_api_key else self.model_config_service.get_api_key_sync(provider_id)
        if not api_key:
            raise ValueError(
                f"No API key configured. Set the embedding API key in RAG Settings, "
                f"or configure an API key for provider '{provider_id}'."
            )

        # Try RAG config base_url first, then fall back to provider base_url
        base_url = config_base_url if config_base_url else self._get_provider_base_url_sync(provider_id)

        kwargs = {
            "model": model_name,
            "api_key": api_key,
        }
        if base_url:
            kwargs["base_url"] = base_url

        kwargs["check_embedding_ctx_length"] = False
        if batch_size:
            kwargs["chunk_size"] = batch_size
        return OpenAIEmbeddings(**kwargs)

    def _get_local_embeddings(self, model_name: str, device: str = "cpu"):
        """
        Get local embeddings using sentence-transformers.

        Args:
            model_name: HuggingFace model name (e.g., all-MiniLM-L6-v2)
            device: Device to run on (cpu, cuda)
        """
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for local embeddings. "
                "Install with: pip install sentence-transformers"
            )

        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
        )

    def _get_local_gguf_embeddings(
        self,
        model_path: str,
        n_ctx: int = 2048,
        n_threads: int = 0,
        n_gpu_layers: int = 0,
        normalize: bool = True,
    ):
        """
        Get local embeddings from a GGUF model using llama-cpp-python.

        Args:
            model_path: GGUF model path (absolute or repo-relative)
            n_ctx: llama.cpp context window
            n_threads: CPU thread count (0 = auto)
            n_gpu_layers: GPU offload layers (0 = CPU only)
            normalize: whether to L2-normalize vectors
        """
        try:
            import llama_cpp  # noqa: F401
        except ImportError:
            raise ImportError(
                "llama-cpp-python is required for local GGUF embeddings. "
                "Install with: ./venv/Scripts/pip install llama-cpp-python"
            )

        return LlamaCppEmbeddings(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            normalize=normalize,
        )
