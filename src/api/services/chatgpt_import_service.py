"""ChatGPT export import service."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .conversation_storage import ConversationStorage


class ChatGPTImportService:
    """Import conversations from ChatGPT export JSON."""

    def __init__(self, storage: ConversationStorage):
        self.storage = storage

    async def import_conversations(
        self,
        conversations: List[Dict[str, Any]],
        context_type: str = "chat",
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import a list of ChatGPT conversations.

        Returns:
            {
                "imported": int,
                "skipped": int,
                "sessions": List[{"session_id": str, "title": str, "message_count": int}],
                "errors": List[str],
            }
        """
        imported_sessions: List[Dict[str, Any]] = []
        errors: List[str] = []
        skipped = 0

        for index, conv in enumerate(conversations):
            try:
                messages = self._extract_messages(conv)
                if not messages:
                    skipped += 1
                    continue

                title = self._extract_title(conv, messages)
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
                    "import_source": "chatgpt",
                    "imported_at": datetime.now().isoformat(),
                }

                created_at = self._extract_created_at(conv)
                if created_at:
                    metadata_updates["created_at"] = created_at

                source_id = conv.get("conversation_id") or conv.get("id")
                if source_id:
                    metadata_updates["import_source_id"] = source_id

                await self.storage.update_session_metadata(
                    session_id,
                    metadata_updates,
                    context_type=context_type,
                    project_id=project_id
                )

                imported_sessions.append({
                    "session_id": session_id,
                    "title": title,
                    "message_count": len(messages),
                })
            except Exception as exc:
                errors.append(f"Conversation #{index + 1}: {exc}")

        return {
            "imported": len(imported_sessions),
            "skipped": skipped,
            "sessions": imported_sessions,
            "errors": errors,
        }

    def _extract_created_at(self, conv: Dict[str, Any]) -> Optional[str]:
        timestamp = conv.get("create_time") or conv.get("update_time")
        if isinstance(timestamp, (int, float)):
            try:
                return datetime.fromtimestamp(timestamp).isoformat()
            except (OSError, ValueError):
                return None
        return None

    def _extract_title(self, conv: Dict[str, Any], messages: List[Dict[str, Any]]) -> str:
        title = str(conv.get("title") or "").strip()
        if not title:
            title = self._title_from_messages(messages)
        if not title:
            title = "Imported Chat"
        return title

    def _title_from_messages(self, messages: List[Dict[str, Any]]) -> str:
        for msg in messages:
            if msg.get("role") == "user":
                content = str(msg.get("content") or "").strip()
                if content:
                    one_line = " ".join(content.splitlines()).strip()
                    if len(one_line) > 60:
                        return f"{one_line[:60]}..."
                    return one_line
        return ""

    def _extract_messages(self, conv: Dict[str, Any]) -> List[Dict[str, Any]]:
        mapping = conv.get("mapping") or {}
        if not isinstance(mapping, dict) or not mapping:
            return []

        current_node = conv.get("current_node")
        if not current_node or current_node not in mapping:
            current_node = self._find_latest_node(mapping)
        if not current_node:
            return []

        path_ids: List[str] = []
        node_id = current_node
        seen: set[str] = set()

        while node_id and node_id not in seen:
            seen.add(node_id)
            node = mapping.get(node_id)
            if not isinstance(node, dict):
                break
            path_ids.append(node_id)
            node_id = node.get("parent")

        path_ids.reverse()

        messages: List[Dict[str, Any]] = []
        for node_id in path_ids:
            node = mapping.get(node_id) or {}
            message = node.get("message")
            if not isinstance(message, dict):
                continue

            role = (message.get("author") or {}).get("role")
            if role not in {"user", "assistant"}:
                continue

            if (message.get("metadata") or {}).get("is_visually_hidden_from_conversation"):
                continue

            content_text = self._extract_content_text(message.get("content"))
            if not content_text.strip():
                continue

            messages.append({
                "role": role,
                "content": content_text,
                "message_id": message.get("id") or node_id,
            })

        return messages

    def _find_latest_node(self, mapping: Dict[str, Any]) -> Optional[str]:
        latest_id = None
        latest_time = -1.0
        for node_id, node in mapping.items():
            if not isinstance(node, dict):
                continue
            message = node.get("message")
            if not isinstance(message, dict):
                continue
            ts = message.get("create_time")
            if isinstance(ts, (int, float)) and ts > latest_time:
                latest_time = ts
                latest_id = node_id
        return latest_id

    def _extract_content_text(self, content: Any) -> str:
        if not isinstance(content, dict):
            return ""

        parts = content.get("parts")
        if isinstance(parts, list):
            texts: List[str] = []
            for part in parts:
                if isinstance(part, str):
                    texts.append(part)
                elif isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str):
                        texts.append(text)
                    else:
                        fallback = part.get("content")
                        if isinstance(fallback, str):
                            texts.append(fallback)
            return "\n".join(texts)

        text = content.get("text")
        if isinstance(text, str):
            return text

        return ""
