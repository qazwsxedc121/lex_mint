"""
Embedding Service

Provides abstraction over API-based and local embedding models.
Uses LangChain Embeddings interface.
"""
import logging
import yaml
from pathlib import Path
from typing import Optional

from .rag_config_service import RagConfigService
from .model_config_service import ModelConfigService

logger = logging.getLogger(__name__)


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
        else:
            model = override_model or config.api_model
            return self._get_api_embeddings(model, config.api_base_url, config.api_key)

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

    def _get_api_embeddings(self, model_id: str, config_base_url: str = "", config_api_key: str = ""):
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

        # If RAG config has dedicated base_url and api_key, use them directly
        if config_base_url and config_api_key:
            # model_id may contain provider: prefix, strip it
            model_name = model_id.split(":", 1)[-1] if ":" in model_id else model_id
            return OpenAIEmbeddings(
                model=model_name,
                api_key=config_api_key,
                base_url=config_base_url,
                check_embedding_ctx_length=False,
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
