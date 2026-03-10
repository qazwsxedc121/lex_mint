"""Compatibility re-export for query transform service."""

from src.infrastructure.retrieval.query_transform_service import (
    QueryTransformResult,
    QueryTransformService,
)

__all__ = ["QueryTransformResult", "QueryTransformService"]
