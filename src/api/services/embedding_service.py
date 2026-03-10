"""Compatibility re-export for embedding service."""

from src.infrastructure.retrieval.embedding_service import EmbeddingService, LlamaCppEmbeddings

__all__ = ["EmbeddingService", "LlamaCppEmbeddings"]
