"""Comparison storage service for multi-model comparison data.

Stores comparison responses in sidecar JSON files alongside conversation markdown files.
"""

import json
import asyncio
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

import aiofiles

from .conversation_storage import ConversationStorage

logger = logging.getLogger(__name__)


class ComparisonStorage:
    """Manages sidecar .compare.json files for multi-model comparison data."""

    def __init__(self, conversation_storage: ConversationStorage):
        self._conversation_storage = conversation_storage
        self._file_locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, file_path: str) -> asyncio.Lock:
        if file_path not in self._file_locks:
            self._file_locks[file_path] = asyncio.Lock()
        return self._file_locks[file_path]

    async def _get_compare_path(
        self, session_id: str, context_type: str = "chat", project_id: Optional[str] = None
    ) -> Optional[Path]:
        """Get the .compare.json path for a session."""
        md_path = await self._conversation_storage._find_session_file(
            session_id, context_type, project_id
        )
        if not md_path:
            return None
        return md_path.with_suffix(".compare.json")

    async def load(
        self, session_id: str, context_type: str = "chat", project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load comparison data for a session.

        Returns:
            Dict mapping assistant_message_id -> {"responses": [...]}
            Returns empty dict if no comparison data exists.
        """
        compare_path = await self._get_compare_path(session_id, context_type, project_id)
        if not compare_path or not compare_path.exists():
            return {}

        try:
            async with aiofiles.open(compare_path, "r", encoding="utf-8") as f:
                content = await f.read()
            return json.loads(content)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to load comparison data for {session_id}: {e}")
            return {}

    async def save(
        self,
        session_id: str,
        assistant_message_id: str,
        responses: List[Dict[str, Any]],
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        """Save comparison responses for an assistant message.

        Args:
            session_id: Session UUID
            assistant_message_id: The assistant message ID this comparison belongs to
            responses: List of model response dicts
            context_type: Context type
            project_id: Project ID
        """
        compare_path = await self._get_compare_path(session_id, context_type, project_id)
        if not compare_path:
            raise FileNotFoundError(f"Session {session_id} not found")

        lock = self._get_lock(str(compare_path))
        async with lock:
            # Load existing data
            data = {}
            if compare_path.exists():
                try:
                    async with aiofiles.open(compare_path, "r", encoding="utf-8") as f:
                        content = await f.read()
                    data = json.loads(content)
                except Exception:
                    data = {}

            # Update with new responses
            data[assistant_message_id] = {"responses": responses}

            # Write back
            async with aiofiles.open(compare_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))

    async def delete(
        self, session_id: str, context_type: str = "chat", project_id: Optional[str] = None
    ) -> None:
        """Delete the sidecar comparison file for a session."""
        compare_path = await self._get_compare_path(session_id, context_type, project_id)
        if compare_path and compare_path.exists():
            compare_path.unlink()
