"""Conversation storage service using Markdown files with YAML frontmatter."""

import asyncio
import frontmatter
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import aiofiles
import uuid
import re

from src.providers.types import TokenUsage, CostInfo
from .conversation_storage_paths import StoragePathResolver, build_project_root_resolver
from .conversation_target_resolver import ConversationSessionTargetResolver
from src.domain.models.group_participant import parse_group_participant


class ConversationStorage:
    """Manages conversation storage in Markdown format.

    Each conversation is stored as a separate .md file with:
    - YAML frontmatter for metadata (session_id, title, created_at, current_step)
    - Markdown body with timestamped messages
    """

    def __init__(
        self,
        conversations_dir: Path,
        project_root_resolver: Optional[Callable[[str], Optional[str]]] = None,
        assistant_service: Any = None,
        model_service: Any = None,
    ):
        """Initialize storage with conversations directory.

        Args:
            conversations_dir: Path to directory for storing conversation files
            project_root_resolver: Optional sync function (project_id) -> root_path
                that resolves a project ID to its filesystem root path.
                When set, project conversations are stored under
                {root_path}/.lex_mint/conversations/ instead of
                conversations/projects/{project_id}/.
        """
        self.conversations_dir = Path(conversations_dir)
        self.conversations_dir.mkdir(exist_ok=True)
        self._project_root_resolver = project_root_resolver
        self._path_resolver = StoragePathResolver(self.conversations_dir, project_root_resolver)
        self._target_resolver = ConversationSessionTargetResolver(
            assistant_service=assistant_service,
            model_service=model_service,
        )
        # Per-file locks to prevent concurrent read-modify-write corruption
        self._file_locks: Dict[str, asyncio.Lock] = {}

    @staticmethod
    def _as_optional_str(value: Any) -> Optional[str]:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned if cleaned else None
        return None

    @staticmethod
    def _as_str(value: Any, default: str = "") -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return default
        return str(value)

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    async def create_session(
        self,
        model_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        target_type: Optional[str] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        temporary: bool = False,
        group_assistants: Optional[List[str]] = None,
        group_mode: Optional[str] = None,
        group_settings: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new conversation session.

        Args:
            model_id: Optional model ID. Supports either a simple ID or a composite
                ID in the form ``provider_id:model_id``.
            assistant_id: Optional assistant ID.
            target_type: Conversation target type ("assistant" or "model")
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Returns:
            session_id: UUID string for the new session

        Raises:
            ValueError: If context parameters are invalid
        """
        resolved_target = await self._target_resolver.resolve_target(
            target_type=target_type,
            assistant_id=assistant_id,
            model_id=model_id,
        )
        assistant_id = resolved_target.assistant_id
        model_id = resolved_target.model_id

        # Get context-specific directory and create if needed
        conversation_dir = self._get_conversation_dir(context_type, project_id)
        conversation_dir.mkdir(parents=True, exist_ok=True)

        session_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_{session_id[:8]}.md"
        filepath = conversation_dir / filename

        # Create file with frontmatter metadata
        post = frontmatter.Post("")
        metadata = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "title": "New Conversation",
            "current_step": 0,
            "model_id": model_id,
            "target_type": resolved_target.target_type,
        }

        # Store assistant_id for newly created sessions.
        if assistant_id:
            metadata["assistant_id"] = assistant_id

        if temporary:
            metadata["temporary"] = True

        if group_assistants is not None:
            normalized_group_assistants: List[str] = []
            seen_group_assistants = set()
            for assistant_id in group_assistants:
                if not isinstance(assistant_id, str):
                    continue
                cleaned = assistant_id.strip()
                if not cleaned or cleaned in seen_group_assistants:
                    continue
                seen_group_assistants.add(cleaned)
                normalized_group_assistants.append(cleaned)

            if len(normalized_group_assistants) < 2:
                raise ValueError("Group chat requires at least 2 unique assistants")

            metadata["group_assistants"] = normalized_group_assistants
            metadata["group_mode"] = (group_mode or "round_robin").strip().lower()
            if group_settings is not None:
                metadata["group_settings"] = group_settings

        post.metadata = metadata

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

        return session_id

    async def get_session(self, session_id: str, context_type: str = "chat", project_id: Optional[str] = None) -> Dict:
        """Load a conversation session.

        Args:
            session_id: Session UUID to load
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Returns:
            Dictionary with session metadata and state:
            {
                "session_id": str,
                "title": str,
                "created_at": str,
                "assistant_id": str,
                "model_id": str,
                "state": {
                    "messages": List[Dict],
                    "current_step": int
                }
            }

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            content = await f.read()

        post = frontmatter.loads(content)
        metadata: Dict[str, Any] = dict(post.metadata or {})

        # Parse messages from markdown content
        messages = self._parse_messages(post.content, session_id)

        # Resolve assistant/model target from explicit canonical metadata only.
        assistant_id = self._as_optional_str(metadata.get("assistant_id"))
        model_id = self._as_optional_str(metadata.get("model_id"))
        target_type = self._as_optional_str(metadata.get("target_type"))
        if target_type not in {"assistant", "model"}:
            raise ValueError(
                "Session metadata is incompatible: target_type must be 'assistant' or 'model'."
            )

        if target_type == "assistant":
            if not assistant_id:
                raise ValueError(
                    "Session metadata is incompatible: assistant target requires assistant_id."
                )
            from src.infrastructure.config.assistant_config_service import AssistantConfigService

            assistant_service = AssistantConfigService()
            assistant = await assistant_service.get_assistant(assistant_id)
            if assistant is None:
                raise ValueError(
                    f"Session assistant '{assistant_id}' no longer exists. "
                    "This session is not compatible with the current runtime."
                )
            model_id = assistant.model_id
        else:
            if not model_id:
                raise ValueError(
                    "Session metadata is incompatible: model target requires model_id."
                )
            if ":" not in model_id:
                from src.infrastructure.config.model_config_service import ModelConfigService

                model_service = ModelConfigService()
                model_obj = await model_service.get_model(model_id)
                if model_obj is None:
                    raise ValueError(
                        f"Session model '{model_id}' no longer exists. "
                        "This session is not compatible with the current runtime."
                    )
                model_id = f"{model_obj.provider_id}:{model_obj.id}"
            assistant_id = None

        result = {
            "session_id": self._as_str(metadata.get("session_id"), session_id),
            "title": self._as_str(metadata.get("title"), "Untitled Conversation"),
            "created_at": self._as_str(metadata.get("created_at")),
            "assistant_id": assistant_id,
            "model_id": model_id,
            "target_type": target_type,
            "target_id": assistant_id if target_type == "assistant" else model_id,
            "param_overrides": self._as_dict(metadata.get("param_overrides")),
            "total_usage": metadata.get("total_usage"),
            "total_cost": metadata.get("total_cost"),
            "temporary": bool(metadata.get("temporary", False)),
            "state": {
                "messages": messages,
                "current_step": self._as_int(metadata.get("current_step"), 0)
            }
        }

        # Include group_assistants if present
        group_assistants = metadata.get("group_assistants")
        if group_assistants:
            result["group_assistants"] = group_assistants
            result["group_mode"] = self._as_str(metadata.get("group_mode"), "round_robin")
            if "group_settings" in metadata:
                result["group_settings"] = metadata.get("group_settings")

        return result

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        attachments: Optional[List[Dict]] = None,
        usage: Optional[TokenUsage] = None,
        cost: Optional[CostInfo] = None,
        sources: Optional[List[Dict]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        assistant_id: Optional[str] = None
    ) -> str:
        """Append a message to conversation file.

        Args:
            session_id: Session UUID
            role: Message role ("user" or "assistant")
            content: Message text content
            attachments: List of file attachment metadata (for user messages)
            usage: Token usage data (for assistant messages)
            cost: Cost information (for assistant messages)
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Returns:
            message_id: The generated UUID for the new message

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        # Generate message ID
        message_id = str(uuid.uuid4())

        # Read existing content
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)
        metadata: Dict[str, Any] = dict(post.metadata or {})

        # Append new message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if role == "user":
            role_display = "User"
        elif role == "assistant":
            role_display = "Assistant"
        elif role == "summary":
            role_display = "Summary"
        else:  # separator
            role_display = "Separator"
        new_message = f"\n## {role_display} ({timestamp})\n{content}\n"

        # Add message_id as HTML comment
        new_message += f"\n<!-- message_id: \"{message_id}\" -->\n"

        # Add assistant_id as HTML comment for group chat messages
        if role == "assistant" and assistant_id:
            new_message += f"<!-- assistant_id: \"{assistant_id}\" -->\n"

        # Add attachment metadata as HTML comments (for user messages)
        if role == "user" and attachments:
            for att in attachments:
                new_message += f"<!-- attachment: {json.dumps(att)} -->\n"

        # Add usage/cost as HTML comments for assistant messages
        if role == "assistant" and usage:
            new_message += f"\n<!-- usage: {json.dumps(usage.model_dump())} -->\n"
            if cost:
                new_message += f"<!-- cost: {json.dumps(cost.model_dump())} -->\n"

        # Add web search sources as HTML comments (for assistant messages)
        if role == "assistant" and sources:
            new_message += f"<!-- sources: {json.dumps(sources, ensure_ascii=False)} -->\n"

        post.content += new_message

        # Update current_step for assistant messages
        if role == "assistant":
            metadata["current_step"] = self._as_int(metadata.get("current_step"), 0) + 1

            # Update session-level usage totals in frontmatter
            if usage:
                total_usage = self._as_dict(metadata.get("total_usage"))
                total_usage["prompt_tokens"] = (
                    self._as_int(total_usage.get("prompt_tokens"), 0) + usage.prompt_tokens
                )
                total_usage["completion_tokens"] = (
                    self._as_int(total_usage.get("completion_tokens"), 0) + usage.completion_tokens
                )
                total_usage["total_tokens"] = (
                    self._as_int(total_usage.get("total_tokens"), 0) + usage.total_tokens
                )
                metadata["total_usage"] = total_usage

            if cost:
                total_cost = self._as_dict(metadata.get("total_cost"))
                if "currency" not in total_cost:
                    total_cost["currency"] = "USD"
                total_cost["total_cost"] = round(
                    self._as_float(total_cost.get("total_cost"), 0.0) + cost.total_cost,
                    8,
                )
                metadata["total_cost"] = total_cost

        # Auto-generate title from first user message
        if self._as_str(metadata.get("title")) in {"\\u65B0\\u5BF9\\u8BDD", "New Conversation", "New Chat"} and role == "user":
            # Clean title: remove special chars, limit length
            clean_title = content.strip().replace('\n', ' ')[:30]
            metadata["title"] = clean_title + ("..." if len(content) > 30 else "")

        post.metadata = metadata

        # Write back to file
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

        return message_id

    async def append_separator(self, session_id: str, context_type: str = "chat", project_id: Optional[str] = None) -> str:
        """
        Append a separator message to conversation.

        Args:
            session_id: Session UUID
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Returns:
            message_id: The generated UUID for the separator

        Raises:
            ValueError: If context parameters are invalid
        """
        return await self.append_message(
            session_id=session_id,
            role="separator",
            content="--- Context cleared ---",
            context_type=context_type,
            project_id=project_id
        )

    async def append_summary(
        self,
        session_id: str,
        content: str,
        compressed_count: int = 0,
        compression_meta: Optional[Dict[str, Any]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None
    ) -> str:
        """
        Append a summary message to conversation.

        Args:
            session_id: Session UUID
            content: Summary text content
            compressed_count: Number of messages that were compressed
            compression_meta: Extra compression metadata to persist on the summary
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Returns:
            message_id: The generated UUID for the summary

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        message_id = str(uuid.uuid4())

        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_message = f"\n## Summary ({timestamp})\n{content}\n"
        new_message += f"\n<!-- message_id: \"{message_id}\" -->\n"
        merged_meta: Dict[str, Any] = {"compressed_count": compressed_count}
        if compression_meta:
            merged_meta.update(compression_meta)
        new_message += f"<!-- compression_meta: {json.dumps(merged_meta)} -->\n"

        post.content += new_message

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

        return message_id

    async def list_sessions(self, context_type: str = "chat", project_id: Optional[str] = None) -> List[Dict]:
        """List all conversation sessions in a specific context.

        Args:
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Returns:
            List of session summaries sorted by creation time (newest first):
            [
                {
                    "session_id": str,
                    "title": str,
                    "created_at": str,
                    "message_count": int
                },
                ...
            ]

        Raises:
            ValueError: If context parameters are invalid
        """
        # Get context-specific directory
        conversation_dir = self._get_conversation_dir(context_type, project_id)

        # Return empty list if directory doesn't exist
        if not conversation_dir.exists():
            return []

        sessions = []
        for filepath in conversation_dir.glob("*.md"):
            try:
                async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                    content = await f.read()

                post = frontmatter.loads(content)

                # Skip temporary sessions
                if post.metadata.get("temporary", False):
                    continue

                # Count messages
                message_count = (
                    post.content.count("## User") +
                    post.content.count("## Assistant")
                )

                # Get file modification time as updated_at
                mtime = os.path.getmtime(filepath)
                updated_at = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                session_entry = {
                    "session_id": post.metadata["session_id"],
                    "title": post.metadata.get("title", "New Chat"),
                    "created_at": post.metadata["created_at"],
                    "updated_at": updated_at,
                    "message_count": message_count,
                    "folder_id": post.metadata.get("folder_id")  # Chat folder ID (optional)
                }

                group_assistants = post.metadata.get("group_assistants")
                if group_assistants:
                    session_entry["group_assistants"] = group_assistants
                    session_entry["group_mode"] = post.metadata.get("group_mode", "round_robin")
                    if "group_settings" in post.metadata:
                        session_entry["group_settings"] = post.metadata.get("group_settings")

                sessions.append(session_entry)
            except Exception as e:
                # Skip corrupted files
                print(f"Warning: Skipping corrupted file {filepath}: {e}")
                continue

        # Sort by updated_at descending (most recently modified first)
        sessions.sort(key=lambda s: s["updated_at"], reverse=True)
        return sessions

    async def search_sessions(self, query: str, context_type: str = "chat", project_id: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """Search sessions by title and message content.

        Args:
            query: Search query string (case-insensitive substring match)
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")
            limit: Maximum number of results to return

        Returns:
            List of matching session summaries with match info
        """
        if not query or not query.strip():
            return []

        query_lower = query.lower().strip()

        conversation_dir = self._get_conversation_dir(context_type, project_id)
        if not conversation_dir.exists():
            return []

        results = []
        for filepath in sorted(conversation_dir.glob("*.md"), reverse=True):
            if len(results) >= limit:
                break
            try:
                async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                    content = await f.read()

                post = frontmatter.loads(content)
                metadata = self._as_dict(post.metadata)

                # Skip temporary sessions
                if bool(metadata.get("temporary", False)):
                    continue

                title = self._as_str(metadata.get("title"))
                session_id = self._as_str(metadata.get("session_id"))
                created_at = self._as_str(metadata.get("created_at"))
                body = post.content

                message_count = (
                    body.count("## User") +
                    body.count("## Assistant")
                )

                # Get file modification time as updated_at
                mtime = os.path.getmtime(filepath)
                updated_at = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                # Check title match
                if query_lower in title.lower():
                    results.append({
                        "session_id": session_id,
                        "title": title,
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "message_count": message_count,
                        "match_type": "title",
                        "match_context": title,
                    })
                    continue

                # Check body content match
                body_lower = body.lower()
                idx = body_lower.find(query_lower)
                if idx != -1:
                    # Extract snippet around match (~80 chars)
                    start = max(0, idx - 30)
                    end = min(len(body), idx + len(query) + 50)
                    snippet = body[start:end].replace('\n', ' ').strip()
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(body):
                        snippet = snippet + "..."

                    results.append({
                        "session_id": session_id,
                        "title": title,
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "message_count": message_count,
                        "match_type": "content",
                        "match_context": snippet,
                    })
            except Exception:
                continue

        return results

    async def truncate_messages_after(self, session_id: str, keep_until_index: int, context_type: str = "chat", project_id: Optional[str] = None):
        """Delete all messages after specified index.

        Args:
            session_id: Session UUID
            keep_until_index: Keep messages up to and including this index.
                            Index -1 means delete all messages.
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        # Read and parse existing file
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)
        messages = self._parse_messages(post.content, session_id)

        # Truncate messages list
        if keep_until_index == -1:
            truncated_messages = []
        else:
            truncated_messages = messages[:keep_until_index + 1]

        # Rebuild markdown content
        new_content = ""
        for msg in truncated_messages:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if msg["role"] == "user":
                role_display = "User"
            elif msg["role"] == "assistant":
                role_display = "Assistant"
            elif msg["role"] == "summary":
                role_display = "Summary"
            else:  # separator
                role_display = "Separator"
            new_content += f"\n## {role_display} ({timestamp})\n{msg['content']}\n"

            # Preserve message_id
            if "message_id" in msg:
                new_content += f"\n<!-- message_id: \"{msg['message_id']}\" -->\n"

            # Preserve attachments (for user messages)
            if "attachments" in msg:
                for att in msg["attachments"]:
                    new_content += f"<!-- attachment: {json.dumps(att)} -->\n"

            # Preserve usage and cost (for assistant messages)
            if "usage" in msg:
                new_content += f"<!-- usage: {json.dumps(msg['usage'])} -->\n"
            if "cost" in msg:
                new_content += f"<!-- cost: {json.dumps(msg['cost'])} -->\n"

            # Preserve compression_meta (for summary messages)
            if "compression_meta" in msg:
                new_content += f"<!-- compression_meta: {json.dumps(msg['compression_meta'])} -->\n"

        post.content = new_content

        # Update current_step (count assistant messages)
        assistant_count = sum(1 for msg in truncated_messages if msg["role"] == "assistant")
        post.metadata["current_step"] = assistant_count

        # Write back to file
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

    async def delete_message(self, session_id: str, message_index: int, context_type: str = "chat", project_id: Optional[str] = None):
        """Delete a single message at specified index.

        Args:
            session_id: Session UUID
            message_index: Index of the message to delete
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Raises:
            FileNotFoundError: If session doesn't exist
            IndexError: If message index is out of range
            ValueError: If context parameters are invalid
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        # Read and parse existing file
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)
        messages = self._parse_messages(post.content, session_id)

        # Validate index
        if message_index < 0 or message_index >= len(messages):
            raise IndexError(f"Message index {message_index} out of range (0-{len(messages)-1})")

        # Remove the message at specified index
        del messages[message_index]

        # Rebuild markdown content
        new_content = ""
        for msg in messages:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if msg["role"] == "user":
                role_display = "User"
            elif msg["role"] == "assistant":
                role_display = "Assistant"
            elif msg["role"] == "summary":
                role_display = "Summary"
            else:  # separator
                role_display = "Separator"
            new_content += f"\n## {role_display} ({timestamp})\n{msg['content']}\n"

            # Preserve message_id
            if "message_id" in msg:
                new_content += f"\n<!-- message_id: \"{msg['message_id']}\" -->\n"

            # Preserve attachments (for user messages)
            if "attachments" in msg:
                for att in msg["attachments"]:
                    new_content += f"<!-- attachment: {json.dumps(att)} -->\n"

            # Preserve usage and cost (for assistant messages)
            if "usage" in msg:
                new_content += f"<!-- usage: {json.dumps(msg['usage'])} -->\n"
            if "cost" in msg:
                new_content += f"<!-- cost: {json.dumps(msg['cost'])} -->\n"

            # Preserve compression_meta (for summary messages)
            if "compression_meta" in msg:
                new_content += f"<!-- compression_meta: {json.dumps(msg['compression_meta'])} -->\n"

        post.content = new_content

        # Update current_step (count assistant messages)
        assistant_count = sum(1 for msg in messages if msg["role"] == "assistant")
        post.metadata["current_step"] = assistant_count

        # Update title if all messages are deleted
        if not messages:
            post.metadata["title"] = "New Chat"

        # Write back to file
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

    async def delete_message_by_id(self, session_id: str, message_id: str, context_type: str = "chat", project_id: Optional[str] = None):
        """Delete a single message by its ID.

        Args:
            session_id: Session UUID
            message_id: UUID of the message to delete
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If message_id is not found or context parameters are invalid
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        # Read and parse existing file
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)
        messages = self._parse_messages(post.content, session_id)

        # Find the message with the given ID
        message_index = None
        for index, msg in enumerate(messages):
            if msg.get("message_id") == message_id:
                message_index = index
                break

        if message_index is None:
            raise ValueError(f"Message with ID {message_id} not found")

        # Use the existing delete_message method
        await self.delete_message(session_id, message_index, context_type, project_id)

    async def update_message_content(self, session_id: str, message_id: str, new_content: str, context_type: str = "chat", project_id: Optional[str] = None):
        """Update the content of a specific message by its ID.

        Args:
            session_id: Session UUID
            message_id: UUID of the message to update
            new_content: New content for the message
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If message_id is not found or context parameters are invalid
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)
        messages = self._parse_messages(post.content, session_id)

        # Find the message with the given ID
        message_index = None
        for index, msg in enumerate(messages):
            if msg.get("message_id") == message_id:
                message_index = index
                break

        if message_index is None:
            raise ValueError(f"Message with ID {message_id} not found")

        # Update the content
        messages[message_index]["content"] = new_content

        # Rebuild markdown content
        new_md_content = ""
        for msg in messages:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if msg["role"] == "user":
                role_display = "User"
            elif msg["role"] == "assistant":
                role_display = "Assistant"
            elif msg["role"] == "summary":
                role_display = "Summary"
            else:
                role_display = "Separator"
            new_md_content += f"\n## {role_display} ({timestamp})\n{msg['content']}\n"

            if "message_id" in msg:
                new_md_content += f"\n<!-- message_id: \"{msg['message_id']}\" -->\n"

            if "attachments" in msg:
                for att in msg["attachments"]:
                    new_md_content += f"<!-- attachment: {json.dumps(att)} -->\n"

            if "usage" in msg:
                new_md_content += f"<!-- usage: {json.dumps(msg['usage'])} -->\n"
            if "cost" in msg:
                new_md_content += f"<!-- cost: {json.dumps(msg['cost'])} -->\n"

            if "compression_meta" in msg:
                new_md_content += f"<!-- compression_meta: {json.dumps(msg['compression_meta'])} -->\n"

        post.content = new_md_content

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

    async def clear_all_messages(self, session_id: str, context_type: str = "chat", project_id: Optional[str] = None):
        """Clear all messages from the conversation.

        Args:
            session_id: Session UUID
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        # Read and parse existing file
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)

        # Clear all content
        post.content = ""

        # Reset current_step
        post.metadata["current_step"] = 0

        # Reset title
        post.metadata["title"] = "New Chat"

        # Reset usage totals
        post.metadata["total_usage"] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        post.metadata["total_cost"] = {
            "total_cost": 0.0,
            "currency": "USD",
        }

        # Write back to file
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

    async def set_messages(self, session_id: str, messages: List[Dict], context_type: str = "chat", project_id: Optional[str] = None):
        """Set the complete message list for a session (replaces all existing messages).

        Args:
            session_id: Session UUID
            messages: List of message dictionaries with 'role' and 'content' keys
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        # Read existing content
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)

        # Rebuild markdown content from messages
        new_content = ""
        for msg in messages:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if msg["role"] == "user":
                role_display = "User"
            elif msg["role"] == "assistant":
                role_display = "Assistant"
            elif msg["role"] == "summary":
                role_display = "Summary"
            else:  # separator
                role_display = "Separator"
            new_content += f"\n## {role_display} ({timestamp})\n{msg['content']}\n"

            # Preserve message_id if present
            if "message_id" in msg:
                new_content += f"\n<!-- message_id: \"{msg['message_id']}\" -->\n"

            # Preserve attachments (for user messages)
            if "attachments" in msg:
                for att in msg["attachments"]:
                    new_content += f"<!-- attachment: {json.dumps(att)} -->\n"

            # Preserve usage and cost (for assistant messages)
            if "usage" in msg:
                new_content += f"<!-- usage: {json.dumps(msg['usage'])} -->\n"
            if "cost" in msg:
                new_content += f"<!-- cost: {json.dumps(msg['cost'])} -->\n"

        post.content = new_content

        # Update current_step (count assistant messages)
        assistant_count = sum(1 for msg in messages if msg["role"] == "assistant")
        post.metadata["current_step"] = assistant_count

        # Update title if all messages are deleted
        if not messages:
            post.metadata["title"] = "New Chat"

        # Write back to file
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

    async def update_session_metadata(self, session_id: str, metadata_updates: dict, context_type: str = "chat", project_id: Optional[str] = None):
        """Update session metadata (frontmatter).

        Args:
            session_id: Session UUID
            metadata_updates: Dictionary of metadata fields to update
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        # Use per-file lock to prevent concurrent read-modify-write corruption
        file_key = str(filepath)
        if file_key not in self._file_locks:
            self._file_locks[file_key] = asyncio.Lock()

        async with self._file_locks[file_key]:
            # Read and parse existing file
            async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                file_content = await f.read()

            post = frontmatter.loads(file_content)

            # Update metadata fields
            for key, value in metadata_updates.items():
                post.metadata[key] = value

            # Write back to file
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(frontmatter.dumps(post))

    async def delete_session(self, session_id: str, context_type: str = "chat", project_id: Optional[str] = None):
        """Delete a conversation session.

        Args:
            session_id: Session UUID to delete
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        filepath.unlink()

        # Also delete sidecar .compare.json if it exists
        compare_path = filepath.with_suffix(".compare.json")
        if compare_path.exists():
            compare_path.unlink()

    async def move_session(
        self,
        session_id: str,
        source_context_type: str = "chat",
        source_project_id: Optional[str] = None,
        target_context_type: str = "chat",
        target_project_id: Optional[str] = None
    ) -> str:
        """Move a session file between contexts (chat/projects).

        Args:
            session_id: Session UUID to move
            source_context_type: Source context type ("chat" or "project")
            source_project_id: Source project ID (required for project context)
            target_context_type: Target context type ("chat" or "project")
            target_project_id: Target project ID (required for project context)

        Returns:
            session_id: Same session ID after move

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid or target is same as source
            FileExistsError: If target already has a session file with same name
        """
        if source_context_type == target_context_type and (source_project_id or None) == (target_project_id or None):
            raise ValueError("Target context is the same as source context")

        source_path = await self._find_session_file(session_id, source_context_type, source_project_id)
        if not source_path:
            raise FileNotFoundError(f"Session {session_id} not found")

        target_dir = self._get_conversation_dir(target_context_type, target_project_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / source_path.name
        if target_path.exists():
            raise FileExistsError(f"Target session file already exists: {target_path}")

        source_compare_path = source_path.with_suffix(".compare.json")
        target_compare_path = target_path.with_suffix(".compare.json")
        if target_compare_path.exists():
            raise FileExistsError(f"Target compare sidecar file already exists: {target_compare_path}")

        shutil.move(str(source_path), str(target_path))
        if source_compare_path.exists():
            shutil.move(str(source_compare_path), str(target_compare_path))

        # Move lock reference to new path if present
        old_key = str(source_path)
        if old_key in self._file_locks:
            self._file_locks[str(target_path)] = self._file_locks.pop(old_key)

        return session_id

    async def copy_session(
        self,
        session_id: str,
        source_context_type: str = "chat",
        source_project_id: Optional[str] = None,
        target_context_type: str = "chat",
        target_project_id: Optional[str] = None,
        title_suffix: str = " (Copy)"
    ) -> str:
        """Copy a session file to another context with a new session ID.

        Args:
            session_id: Session UUID to copy
            source_context_type: Source context type ("chat" or "project")
            source_project_id: Source project ID (required for project context)
            target_context_type: Target context type ("chat" or "project")
            target_project_id: Target project ID (required for project context)
            title_suffix: Suffix to append to the copied session title

        Returns:
            new_session_id: New session UUID for the copied session

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        source_path = await self._find_session_file(session_id, source_context_type, source_project_id)
        if not source_path:
            raise FileNotFoundError(f"Session {session_id} not found")

        target_dir = self._get_conversation_dir(target_context_type, target_project_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(source_path, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)
        new_session_id = str(uuid.uuid4())
        post.metadata["session_id"] = new_session_id
        post.metadata["created_at"] = datetime.now().isoformat()
        original_title = post.metadata.get("title", "New Chat")
        post.metadata["title"] = f"{original_title}{title_suffix}"
        # Copied sessions should be permanent
        if "temporary" in post.metadata:
            post.metadata["temporary"] = False

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_{new_session_id[:8]}.md"
        target_path = target_dir / filename

        async with aiofiles.open(target_path, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

        source_compare_path = source_path.with_suffix(".compare.json")
        if source_compare_path.exists():
            target_compare_path = target_path.with_suffix(".compare.json")
            shutil.copy2(str(source_compare_path), str(target_compare_path))

        return new_session_id

    async def cleanup_temporary_sessions(self):
        """Delete all temporary session files across all contexts.

        Called at backend startup to clean up leftover temp files.
        """
        cleaned = 0
        # Scan chat directory
        chat_dir = self.conversations_dir / "chat"
        if chat_dir.exists():
            for filepath in chat_dir.glob("*.md"):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        post = frontmatter.load(f)

                    if post.metadata.get("temporary", False):
                        filepath.unlink()
                        compare_path = filepath.with_suffix(".compare.json")
                        if compare_path.exists():
                            compare_path.unlink()
                        cleaned += 1
                except Exception:
                    continue

        # Scan project directories via project root resolver
        if self._project_root_resolver:
            try:
                import yaml
                from ..config import settings
                config_path = settings.projects_config_path
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                    if data:
                        for proj in data.get('projects', []):
                            root_path = proj.get('root_path')
                            if root_path:
                                proj_conv_dir = Path(root_path) / ".lex_mint" / "conversations"
                                if proj_conv_dir.exists():
                                    for filepath in proj_conv_dir.glob("*.md"):
                                        try:
                                            with open(filepath, 'r', encoding='utf-8') as f:
                                                post = frontmatter.load(f)
                                            if post.metadata.get("temporary", False):
                                                filepath.unlink()
                                                compare_path = filepath.with_suffix(".compare.json")
                                                if compare_path.exists():
                                                    compare_path.unlink()
                                                cleaned += 1
                                        except Exception:
                                            continue
            except Exception:
                pass

        return cleaned

    async def convert_to_permanent(self, session_id: str, context_type: str = "chat", project_id: Optional[str] = None):
        """Convert a temporary session to a permanent one.

        Removes the 'temporary' key from frontmatter.

        Args:
            session_id: Session UUID
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)

        # Remove temporary flag
        if "temporary" in post.metadata:
            del post.metadata["temporary"]

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

    @staticmethod
    def _extract_model_chat_template_overrides(model_obj: Any) -> Dict[str, Any]:
        """Build session param overrides from model chat_template."""
        return ConversationSessionTargetResolver.extract_model_chat_template_overrides(model_obj)

    async def update_session_target(
        self,
        session_id: str,
        *,
        target_type: str,
        assistant_id: Optional[str] = None,
        model_id: Optional[str] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ):
        """Update session target to assistant or model."""
        filepath = await self._find_session_file(session_id, context_type, project_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()
        post = frontmatter.loads(file_content)

        await self._target_resolver.apply_target_metadata(
            post,
            target_type=target_type,
            assistant_id=assistant_id,
            model_id=model_id,
        )

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

    async def update_session_model(self, session_id: str, model_id: str, context_type: str = "chat", project_id: Optional[str] = None):
        """Wrapper for setting model target."""
        await self.update_session_target(
            session_id,
            target_type="model",
            model_id=model_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def update_session_assistant(self, session_id: str, assistant_id: str, context_type: str = "chat", project_id: Optional[str] = None):
        """Wrapper for setting assistant target."""
        await self.update_session_target(
            session_id,
            target_type="assistant",
            assistant_id=assistant_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def update_group_assistants(self, session_id: str, group_assistants: List[str], context_type: str = "chat", project_id: Optional[str] = None):
        """Update the group_assistants list for a session.

        Args:
            session_id: Session UUID
            group_assistants: List of assistant IDs (must have 2+ entries)
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If less than 2 assistants provided
        """
        normalized_group_assistants: List[str] = []
        seen_group_assistants = set()
        for participant_token in group_assistants:
            if not isinstance(participant_token, str):
                continue
            try:
                participant = parse_group_participant(participant_token)
            except ValueError:
                continue
            stable_token = participant.token
            if stable_token in seen_group_assistants:
                continue
            seen_group_assistants.add(stable_token)
            normalized_group_assistants.append(stable_token)

        if len(normalized_group_assistants) < 2:
            raise ValueError("Group chat requires at least 2 unique participants")

        await self.update_session_metadata(
            session_id=session_id,
            metadata_updates={"group_assistants": normalized_group_assistants},
            context_type=context_type,
            project_id=project_id
        )

    async def update_session_folder(self, session_id: str, folder_id: Optional[str], context_type: str = "chat", project_id: Optional[str] = None):
        """Update session's folder assignment.

        Args:
            session_id: Session UUID
            folder_id: Folder ID to assign (None to remove from folder)
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If context parameters are invalid
        """
        await self.update_session_metadata(
            session_id=session_id,
            metadata_updates={"folder_id": folder_id},
            context_type=context_type,
            project_id=project_id
        )

    def _get_conversation_dir(self, context_type: str = "chat", project_id: Optional[str] = None) -> Path:
        """Get the conversation directory for a specific context.

        Args:
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Returns:
            Path to the conversation directory for this context

        Raises:
            ValueError: If context_type is invalid or project_id is missing/invalid
        """
        return self._path_resolver.get_conversation_dir(context_type, project_id)

    async def _find_session_file(self, session_id: str, context_type: str = "chat", project_id: Optional[str] = None) -> Optional[Path]:
        """Find the file path for a session by its ID.

        Args:
            session_id: Session UUID to find
            context_type: Context type ("chat" or "project")
            project_id: Project ID (required when context_type="project")

        Returns:
            Path to session file, or None if not found

        Raises:
            ValueError: If context parameters are invalid
        """
        return await self._path_resolver.find_session_file(session_id, context_type, project_id)

    def _parse_messages(self, content: str, session_id: str) -> List[Dict]:
        """Parse messages from markdown content.

        Args:
            content: Markdown body content (without frontmatter)
            session_id: Session ID for generating fallback message IDs

        Returns:
            List of message dicts:
            [{"role": "user/assistant", "content": "...", "message_id": "...", "attachments": [...], "usage": {...}, "cost": {...}}, ...]
        """
        messages = []
        lines = content.split('\n')
        current_message = None

        for line in lines:
            # Detect message headers (## User/Assistant/Separator/Summary (timestamp))
            if line.startswith("## User (") or line.startswith("## Assistant (") or line.startswith("## Separator (") or line.startswith("## Summary ("):
                # Save previous message
                if current_message:
                    messages.append(current_message)

                # Start new message
                if line.startswith("## User"):
                    role = "user"
                elif line.startswith("## Assistant"):
                    role = "assistant"
                elif line.startswith("## Summary"):
                    role = "summary"
                else:  # Separator
                    role = "separator"

                # Extract timestamp from header
                ts_match = re.search(r'\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)', line)
                created_at = ts_match.group(1) if ts_match else None

                current_message = {"role": role, "content": "", "created_at": created_at}
            elif current_message is not None:
                # Parse usage/cost/attachment/message_id HTML comments
                usage_match = re.match(r'^<!-- usage: (.+) -->$', line.strip())
                cost_match = re.match(r'^<!-- cost: (.+) -->$', line.strip())
                attachment_match = re.match(r'^<!-- attachment: (.+) -->$', line.strip())
                message_id_match = re.match(r'^<!-- message_id: "(.+)" -->$', line.strip())
                assistant_id_match = re.match(r'^<!-- assistant_id: "(.+)" -->$', line.strip())
                sources_match = re.match(r'^<!-- sources: (.+) -->$', line.strip())
                compression_meta_match = re.match(r'^<!-- compression_meta: (.+) -->$', line.strip())

                if usage_match:
                    try:
                        current_message["usage"] = json.loads(usage_match.group(1))
                    except json.JSONDecodeError:
                        pass
                elif cost_match:
                    try:
                        current_message["cost"] = json.loads(cost_match.group(1))
                    except json.JSONDecodeError:
                        pass
                elif attachment_match:
                    try:
                        if "attachments" not in current_message:
                            current_message["attachments"] = []
                        current_message["attachments"].append(
                            json.loads(attachment_match.group(1))
                        )
                    except json.JSONDecodeError:
                        pass
                elif message_id_match:
                    current_message["message_id"] = message_id_match.group(1)
                elif assistant_id_match:
                    current_message["assistant_id"] = assistant_id_match.group(1)
                elif sources_match:
                    try:
                        current_message["sources"] = json.loads(sources_match.group(1))
                    except json.JSONDecodeError:
                        pass
                elif compression_meta_match:
                    try:
                        current_message["compression_meta"] = json.loads(compression_meta_match.group(1))
                    except json.JSONDecodeError:
                        pass
                else:
                    # Append line to current message content
                    # Skip empty lines at the start
                    if current_message["content"] or line.strip():
                        current_message["content"] += line + "\n"

        # Save last message
        if current_message:
            messages.append(current_message)

        # Clean up: strip trailing whitespace and generate fallback message IDs
        for index, msg in enumerate(messages):
            msg["content"] = msg["content"].strip()
            # Generate fallback UUID if message_id not found.
            if "message_id" not in msg:
                msg["message_id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}:{index}"))

        return messages


def create_storage_with_project_resolver(
    conversations_dir,
    *,
    project_service: Any = None,
    assistant_service: Any = None,
    model_service: Any = None,
) -> ConversationStorage:
    """Create a ConversationStorage with a sync resolver that reads projects_config.yaml.

    The resolver maps project_id -> root_path by reading the projects config file.
    Project conversations are then stored at {root_path}/.lex_mint/conversations/.

    Args:
        conversations_dir: Path to the base conversations directory

    Returns:
        ConversationStorage instance with project root resolver configured
    """
    if project_service is None:
        from src.infrastructure.config.project_service import ProjectService

        project_service = ProjectService()

    return ConversationStorage(
        conversations_dir,
        project_root_resolver=build_project_root_resolver(project_service),
        assistant_service=assistant_service,
        model_service=model_service,
    )
