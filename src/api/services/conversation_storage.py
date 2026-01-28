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

    async def create_session(
        self,
        model_id: Optional[str] = None,
        assistant_id: Optional[str] = None
    ) -> str:
        """Create a new conversation session.

        Args:
            model_id: 可选的模型 ID，支持简单ID或复合ID (provider_id:model_id)
                     如果未指定则使用默认模型（向后兼容）
            assistant_id: 可选的助手 ID，优先使用（新方式）

        Returns:
            session_id: UUID string for the new session
        """
        # 优先使用 assistant_id（新方式）
        if assistant_id:
            # 验证助手存在
            from .assistant_config_service import AssistantConfigService
            assistant_service = AssistantConfigService()
            assistant = await assistant_service.get_assistant(assistant_id)
            if not assistant:
                raise ValueError(f"Assistant '{assistant_id}' not found")
            # 新会话：使用助手 + 存储关联的模型ID（用于显示）
            model_id = assistant.model_id
        elif model_id:
            # 提供了 model_id 但没有 assistant_id（向后兼容）
            if ':' not in model_id:
                # 简单ID转换为复合ID
                from .model_config_service import ModelConfigService
                model_service = ModelConfigService()
                model_obj = await model_service.get_model(model_id)
                if model_obj:
                    model_id = f"{model_obj.provider_id}:{model_obj.id}"
        else:
            # 都没有提供：使用默认助手
            from .assistant_config_service import AssistantConfigService
            assistant_service = AssistantConfigService()
            default_assistant = await assistant_service.get_default_assistant()
            assistant_id = default_assistant.id
            model_id = default_assistant.model_id

        session_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_{session_id[:8]}.md"
        filepath = self.conversations_dir / filename

        # Create file with frontmatter metadata
        post = frontmatter.Post("")
        metadata = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "title": "新对话",
            "current_step": 0,
            "model_id": model_id  # 存储复合ID格式（向后兼容）
        }

        # 新会话：存储 assistant_id
        if assistant_id:
            metadata["assistant_id"] = assistant_id

        post.metadata = metadata

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
                "assistant_id": str,  # NEW: 助手ID（优先）
                "model_id": str,       # 向后兼容
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

        # 向后兼容逻辑：确定使用的助手和模型
        assistant_id = post.metadata.get("assistant_id")
        model_id = post.metadata.get("model_id")

        if assistant_id:
            # 新会话：已有 assistant_id
            # 验证助手存在，获取最新配置
            from .assistant_config_service import AssistantConfigService
            assistant_service = AssistantConfigService()
            assistant = await assistant_service.get_assistant(assistant_id)
            if assistant:
                model_id = assistant.model_id  # 同步最新的模型ID
            else:
                # 助手已被删除，回退到默认助手
                default_assistant = await assistant_service.get_default_assistant()
                assistant_id = default_assistant.id
                model_id = default_assistant.model_id
        elif model_id:
            # 旧会话：只有 model_id，创建临时助手标识
            # 不实际创建 Assistant 对象，只返回特殊标识
            assistant_id = f"__legacy_model_{model_id.replace(':', '_')}"

            # 确保 model_id 是复合格式（向后兼容简单ID）
            if ':' not in model_id:
                from .model_config_service import ModelConfigService
                model_service = ModelConfigService()
                model_obj = await model_service.get_model(model_id)
                if model_obj:
                    model_id = f"{model_obj.provider_id}:{model_obj.id}"
        else:
            # 既没有 assistant_id 也没有 model_id：使用默认助手
            from .assistant_config_service import AssistantConfigService
            assistant_service = AssistantConfigService()
            default_assistant = await assistant_service.get_default_assistant()
            assistant_id = default_assistant.id
            model_id = default_assistant.model_id

        return {
            "session_id": post.metadata["session_id"],
            "title": post.metadata.get("title", "未命名对话"),
            "created_at": post.metadata["created_at"],
            "assistant_id": assistant_id,  # 返回助手ID
            "model_id": model_id,           # 返回复合ID格式（向后兼容）
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

    async def truncate_messages_after(self, session_id: str, keep_until_index: int):
        """Delete all messages after specified index.

        Args:
            session_id: Session UUID
            keep_until_index: Keep messages up to and including this index.
                            Index -1 means delete all messages.

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        filepath = await self._find_session_file(session_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        # Read and parse existing file
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)
        messages = self._parse_messages(post.content)

        # Truncate messages list
        if keep_until_index == -1:
            truncated_messages = []
        else:
            truncated_messages = messages[:keep_until_index + 1]

        # Rebuild markdown content
        new_content = ""
        for msg in truncated_messages:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            role_display = "User" if msg["role"] == "user" else "Assistant"
            new_content += f"\n## {role_display} ({timestamp})\n{msg['content']}\n"

        post.content = new_content

        # Update current_step (count assistant messages)
        assistant_count = sum(1 for msg in truncated_messages if msg["role"] == "assistant")
        post.metadata["current_step"] = assistant_count

        # Write back to file
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

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

    async def update_session_model(self, session_id: str, model_id: str):
        """更新会话使用的模型.

        Args:
            session_id: 会话 UUID
            model_id: 新的模型 ID

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        filepath = await self._find_session_file(session_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        # 读取现有内容
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)
        post.metadata["model_id"] = model_id

        # 写回文件
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

    async def update_session_assistant(self, session_id: str, assistant_id: str):
        """更新会话使用的助手.

        Args:
            session_id: 会话 UUID
            assistant_id: 新的助手 ID

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If assistant doesn't exist
        """
        filepath = await self._find_session_file(session_id)
        if not filepath:
            raise FileNotFoundError(f"Session {session_id} not found")

        # 验证助手存在并获取关联的模型
        from .assistant_config_service import AssistantConfigService
        assistant_service = AssistantConfigService()
        assistant = await assistant_service.get_assistant(assistant_id)
        if not assistant:
            raise ValueError(f"Assistant '{assistant_id}' not found")

        # 读取现有内容
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            file_content = await f.read()

        post = frontmatter.loads(file_content)
        post.metadata["assistant_id"] = assistant_id
        post.metadata["model_id"] = assistant.model_id  # 同步更新模型ID

        # 写回文件
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(frontmatter.dumps(post))

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
