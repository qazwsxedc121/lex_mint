"""Markdown conversation import service."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .conversation_storage import ConversationStorage


class MarkdownImportService:
    """Import a conversation from a Markdown file."""

    def __init__(self, storage: ConversationStorage):
        self.storage = storage

    async def import_markdown(
        self,
        markdown_text: str,
        filename: Optional[str] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import a single Markdown conversation.

        Returns:
            {
                "imported": int,
                "skipped": int,
                "sessions": List[{"session_id": str, "title": str, "message_count": int}],
                "errors": List[str],
            }
        """
        title, messages = self._parse_markdown(markdown_text, filename)
        if not messages:
            return {
                "imported": 0,
                "skipped": 1,
                "sessions": [],
                "errors": ["No user/assistant messages found in markdown file."],
            }

        session_id = await self.storage.create_session(
            context_type=context_type,
            project_id=project_id
        )

        await self.storage.set_messages(
            session_id,
            messages,
            context_type=context_type,
            project_id=project_id
        )

        metadata_updates = {
            "title": title,
            "import_source": "markdown",
            "imported_at": datetime.now().isoformat(),
        }
        await self.storage.update_session_metadata(
            session_id,
            metadata_updates,
            context_type=context_type,
            project_id=project_id
        )

        return {
            "imported": 1,
            "skipped": 0,
            "sessions": [{
                "session_id": session_id,
                "title": title,
                "message_count": len(messages),
            }],
            "errors": [],
        }

    def _parse_markdown(
        self,
        markdown_text: str,
        filename: Optional[str]
    ) -> tuple[str, List[Dict[str, Any]]]:
        lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        title = self._extract_title(lines, filename)

        messages: List[Dict[str, Any]] = []
        current_role: Optional[str] = None
        current_lines: List[str] = []

        for line in lines:
            role = self._detect_role_heading(line)
            if role:
                if current_role is not None:
                    content = self._finalize_content(current_lines)
                    if content:
                        messages.append({"role": current_role, "content": content})
                current_role = role
                current_lines = []
                continue

            if current_role is None:
                continue

            if line.strip() == "---":
                continue

            current_lines.append(line)

        if current_role is not None:
            content = self._finalize_content(current_lines)
            if content:
                messages.append({"role": current_role, "content": content})

        return title, messages

    def _extract_title(self, lines: List[str], filename: Optional[str]) -> str:
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                if title:
                    return title
                break

        if filename:
            stem = Path(filename).stem.strip()
            if stem:
                return stem

        return "Imported Markdown"

    def _detect_role_heading(self, line: str) -> Optional[str]:
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            return None

        lower_line = stripped.lower()
        if "assistant" in lower_line or "\u52a9\u624b" in stripped:
            return "assistant"
        if "user" in lower_line or "\u7528\u6237" in stripped:
            return "user"
        return None

    def _finalize_content(self, lines: List[str]) -> str:
        text = "\n".join(lines).strip()
        return text
