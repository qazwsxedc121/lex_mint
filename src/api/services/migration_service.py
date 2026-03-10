"""Compatibility re-export for project conversation migration service."""

from src.infrastructure.storage.migration_service import migrate_project_conversations

__all__ = ["migrate_project_conversations"]
