"""Compatibility re-export for local llama-cpp service."""

from src.infrastructure.llm.local_llama_cpp_service import (
    LocalLlamaCppService,
    discover_local_gguf_models,
    local_llm_models_dir,
)

__all__ = ["LocalLlamaCppService", "discover_local_gguf_models", "local_llm_models_dir"]
