"""Conversation storage service using Markdown files with YAML frontmatter."""

import frontmatter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import aiofiles
import uuid
import re


class ConversationStorage:
    """Manages conversation storage in Markdown format.

    Each conversation is stored as a separate .md file with:
    - YAML frontmatter for metadata (session_id, title, created_at, current_step)
    - Markdown body with timestamped messages
    """

    def __init__(self, conversations_dir: Path):
        """Initialize storage with conversations directory.

        Args:
            conversations_dir: Path to directory for storing conversation files
        """
        self.conversations_dir = Path(conversations_dir)
        self.conversations_dir.mkdir(exist_ok=True)

    async def create_session(self) -> str:
        """Create a new conversation session.

        Returns:
            session_id: UUID string for the new session
        """
        session_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_{session_id[:8]}.md"
        filepath = self.conversations_dir / filename

        # Create file with frontmatter metadata
        post = frontmatter.Post("")
        post.metadata = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "title": "新对话",
            "current_step": 0
        }

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

        return session_id

    async def get_session(self, session_id: str) -> Dict:
        """Load a conversation session.

        Args:
            session_id: Session UUID to load

        Returns:
            Dictionary with session metadata and state:
            {
                "session_id": str,
                "title": str,
                "created_at": str,
                "state": {
                    "messages": List[Dict],
                    "current_step": int
                }
            }

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        filepath = await self._find_session_file(session_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            content = await f.read()

        post = frontmatter.loads(content)

        # Parse messages from markdown content
        messages = self._parse_messages(post.content)

        return {
            "session_id": post.metadata["session_id"],
            "title": post.metadata.get("title", "未命名对话"),
            "created_at": post.metadata["created_at"],
            "state": {
                "messages": messages,
                "current_step": post.metadata.get("current_step", 0)
            }
        }

    async def append_message(self, session_id: str, role: str, content: str):
        """Append a message to conversation file.

        Args:
            session_id: Session UUID
            role: Message role ("user" or "assistant")
            content: Message text content

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        filepath = await self._find_session_file(session_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        # Read existing content
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)

        # Append new message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        role_display = "User" if role == "user" else "Assistant"
        new_message = f"\n## {role_display} ({timestamp})\n{content}\n"

        post.content += new_message

        # Update current_step for assistant messages
        if role == "assistant":
            post.metadata["current_step"] = post.metadata.get("current_step", 0) + 1

        # Auto-generate title from first user message
        if post.metadata.get("title") == "新对话" and role == "user":
            # Clean title: remove special chars, limit length
            clean_title = content.strip().replace('\n', ' ')[:30]
            post.metadata["title"] = clean_title + ("..." if len(content) > 30 else "")

        # Write back to file
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

    async def list_sessions(self) -> List[Dict]:
        """List all conversation sessions.

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
        """
        sessions = []
        for filepath in sorted(self.conversations_dir.glob("*.md"), reverse=True):
            try:
                async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                    content = await f.read()

                post = frontmatter.loads(content)

                # Count messages
                message_count = (
                    post.content.count("## User") +
                    post.content.count("## Assistant")
                )

                sessions.append({
                    "session_id": post.metadata["session_id"],
                    "title": post.metadata.get("title", "未命名对话"),
                    "created_at": post.metadata["created_at"],
                    "message_count": message_count
                })
            except Exception as e:
                # Skip corrupted files
                print(f"Warning: Skipping corrupted file {filepath}: {e}")
                continue

        return sessions

    async def delete_session(self, session_id: str):
        """Delete a conversation session.

        Args:
            session_id: Session UUID to delete

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        filepath = await self._find_session_file(session_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        filepath.unlink()

    async def _find_session_file(self, session_id: str) -> Optional[Path]:
        """Find the file path for a session by its ID.

        Args:
            session_id: Session UUID to find

        Returns:
            Path to session file, or None if not found
        """
        # Quick path: check if filename contains session_id prefix
        for filepath in self.conversations_dir.glob(f"*_{session_id[:8]}.md"):
            # Verify by reading metadata
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    post = frontmatter.load(f)
                    if post.metadata.get("session_id") == session_id:
                        return filepath
            except Exception:
                continue

        # Fallback: scan all files
        for filepath in self.conversations_dir.glob("*.md"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    post = frontmatter.load(f)
                    if post.metadata.get("session_id") == session_id:
                        return filepath
            except Exception:
                continue

        return None

    def _parse_messages(self, content: str) -> List[Dict]:
        """Parse messages from markdown content.

        Args:
            content: Markdown body content (without frontmatter)

        Returns:
            List of message dicts: [{"role": "user/assistant", "content": "..."}, ...]
        """
        messages = []
        lines = content.split('\n')
        current_message = None

        for line in lines:
            # Detect message headers (## User/Assistant (timestamp))
            if line.startswith("## User (") or line.startswith("## Assistant ("):
                # Save previous message
                if current_message:
                    messages.append(current_message)

                # Start new message
                role = "user" if line.startswith("## User") else "assistant"
                current_message = {"role": role, "content": ""}
            elif current_message is not None:
                # Append line to current message content
                # Skip empty lines at the start
                if current_message["content"] or line.strip():
                    current_message["content"] += line + "\n"

        # Save last message
        if current_message:
            messages.append(current_message)

        # Clean up: strip trailing whitespace
        for msg in messages:
            msg["content"] = msg["content"].strip()

        return messages
