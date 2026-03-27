"""Path resolution helpers for markdown-backed conversation storage."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import frontmatter


class StoragePathResolver:
    """Resolve storage roots and locate session files."""

    def __init__(
        self,
        conversations_dir: Path,
        project_root_resolver: Optional[Callable[[str], Optional[str]]] = None,
    ):
        self.conversations_dir = Path(conversations_dir)
        self.project_root_resolver = project_root_resolver

    def get_conversation_dir(self, context_type: str = "chat", project_id: Optional[str] = None) -> Path:
        if context_type not in ["chat", "project"]:
            raise ValueError(f"Invalid context_type: {context_type}. Must be 'chat' or 'project'")

        if context_type == "project":
            if not project_id:
                raise ValueError("project_id is required for project context")
            if not project_id.strip():
                raise ValueError("project_id cannot be empty")

        if context_type == "chat":
            return self.conversations_dir / "chat"

        assert project_id is not None
        if self.project_root_resolver:
            root_path = self.project_root_resolver(project_id)
            if root_path:
                return Path(root_path) / ".lex_mint" / "conversations"
        raise ValueError(f"Project '{project_id}' not found or project root resolver not configured")

    async def find_session_file(
        self,
        session_id: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> Optional[Path]:
        search_dir = self.get_conversation_dir(context_type, project_id)
        if not search_dir.exists():
            return None

        for filepath in search_dir.glob(f"*_{session_id[:8]}.md"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    post = frontmatter.load(f)
                if post.metadata.get("session_id") == session_id:
                    return filepath
            except Exception:
                continue

        for filepath in search_dir.glob("*.md"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    post = frontmatter.load(f)
                if post.metadata.get("session_id") == session_id:
                    return filepath
            except Exception:
                continue

        return None


def build_project_root_resolver(project_service: object) -> Callable[[str], Optional[str]]:
    """Build a sync project root resolver from ProjectService-like objects."""

    def resolve_project_root(project_id: str) -> Optional[str]:
        resolver = getattr(project_service, "resolve_project_root", None)
        if callable(resolver):
            resolved_path = resolver(project_id)
            return resolved_path if isinstance(resolved_path, str) else None
        return None

    return resolve_project_root
