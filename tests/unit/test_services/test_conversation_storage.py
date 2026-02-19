"""Unit tests for ConversationStorage service."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, AsyncMock, Mock

from src.api.services.conversation_storage import ConversationStorage
from src.providers.types import TokenUsage, CostInfo


class TestConversationStorage:
    """Test cases for ConversationStorage class."""

    @pytest.mark.asyncio
    async def test_create_session(self, temp_conversation_dir, mock_assistant_service):
        """Test creating a new conversation session."""
        # Mock the class where it's imported in the function
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            storage = ConversationStorage(temp_conversation_dir)

            # Create session with assistant_id
            session_id = await storage.create_session(assistant_id="default")

            assert session_id is not None
            assert len(session_id) == 36  # UUID format

            # Verify file was created
            files = list((temp_conversation_dir / "chat").glob("*.md"))
            assert len(files) == 1

            # Load and verify session
            session = await storage.get_session(session_id)
            assert session["session_id"] == session_id
            assert session["assistant_id"] == "default"
            assert session["model_id"] == "deepseek:deepseek-chat"
            assert session["title"] == "新对话"
            assert session["state"]["current_step"] == 0
            assert session["state"]["messages"] == []

    @pytest.mark.asyncio
    async def test_create_session_with_model_id_legacy(self, temp_conversation_dir, mock_assistant_service):
        """Test creating session with model_id (legacy mode)."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            with patch('src.api.services.model_config_service.ModelConfigService') as mock_model_service:
                # Mock model service
                mock_model = Mock()  # Use Mock instead of AsyncMock
                mock_model.id = "deepseek-chat"
                mock_model.provider_id = "deepseek"

                mock_service_instance = Mock()
                mock_service_instance.get_model = AsyncMock(return_value=mock_model)
                mock_model_service.return_value = mock_service_instance

                storage = ConversationStorage(temp_conversation_dir)
                session_id = await storage.create_session(model_id="deepseek-chat")

                session = await storage.get_session(session_id)
                assert session["model_id"] == "deepseek:deepseek-chat"

    @pytest.mark.asyncio
    async def test_create_group_session_with_group_settings(self, temp_conversation_dir, mock_assistant_service):
        """Group settings are persisted and returned with session payload."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            storage = ConversationStorage(temp_conversation_dir)
            session_id = await storage.create_session(
                assistant_id="default",
                group_assistants=["a1", "a2"],
                group_mode="committee",
                group_settings={
                    "version": 1,
                    "committee": {
                        "supervisor_id": "a2",
                        "policy": {"max_rounds": 8},
                    },
                },
            )

            session = await storage.get_session(session_id)
            assert session["group_assistants"] == ["a1", "a2"]
            assert session["group_mode"] == "committee"
            assert session["group_settings"]["committee"]["supervisor_id"] == "a2"
            assert session["group_settings"]["committee"]["policy"]["max_rounds"] == 8

    @pytest.mark.asyncio
    async def test_append_message_user(self, temp_conversation_dir, mock_assistant_service):
        """Test appending user message."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            storage = ConversationStorage(temp_conversation_dir)
            session_id = await storage.create_session(assistant_id="default")

            # Append user message
            await storage.append_message(
                session_id=session_id,
                role="user",
                content="What is Python?"
            )

            # Verify message was added
            session = await storage.get_session(session_id)
            assert len(session["state"]["messages"]) == 1
            assert session["state"]["messages"][0]["role"] == "user"
            assert session["state"]["messages"][0]["content"] == "What is Python?"

            # Title should be auto-generated from first user message
            assert session["title"] == "What is Python?"

    @pytest.mark.asyncio
    async def test_append_message_assistant_with_usage(self, temp_conversation_dir, mock_assistant_service):
        """Test appending assistant message with token usage and cost."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            storage = ConversationStorage(temp_conversation_dir)
            session_id = await storage.create_session(assistant_id="default")

            # Add user message first
            await storage.append_message(session_id, "user", "Hello")

            # Add assistant message with usage
            usage = TokenUsage(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30
            )
            cost = CostInfo(
                total_cost=0.0015,
                currency="USD"
            )

            await storage.append_message(
                session_id=session_id,
                role="assistant",
                content="Hi there!",
                usage=usage,
                cost=cost
            )

            # Verify
            session = await storage.get_session(session_id)
            assert len(session["state"]["messages"]) == 2
            assert session["state"]["messages"][1]["role"] == "assistant"
            assert session["state"]["messages"][1]["content"] == "Hi there!"
            assert session["state"]["current_step"] == 1

            # Check usage data
            assert "usage" in session["state"]["messages"][1]
            assert session["state"]["messages"][1]["usage"]["total_tokens"] == 30

            # Check session-level totals
            assert session["total_usage"]["total_tokens"] == 30
            assert session["total_cost"]["total_cost"] == 0.0015

    @pytest.mark.asyncio
    async def test_list_sessions(self, temp_conversation_dir, mock_assistant_service):
        """Test listing all sessions."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            storage = ConversationStorage(temp_conversation_dir)

            # Create multiple sessions
            session1 = await storage.create_session(assistant_id="default")
            session2 = await storage.create_session(assistant_id="default")

            # Add messages
            await storage.append_message(session1, "user", "Test 1")
            await storage.append_message(session1, "assistant", "Response 1")
            await storage.append_message(session2, "user", "Test 2")

            # List sessions
            sessions = await storage.list_sessions()

            assert len(sessions) == 2
            # Check that both sessions are in the list
            session_ids = {s["session_id"] for s in sessions}
            assert session1 in session_ids
            assert session2 in session_ids

            # Check message counts
            session1_data = next(s for s in sessions if s["session_id"] == session1)
            session2_data = next(s for s in sessions if s["session_id"] == session2)
            assert session1_data["message_count"] == 2
            assert session2_data["message_count"] == 1

    @pytest.mark.asyncio
    async def test_truncate_messages(self, temp_conversation_dir, mock_assistant_service):
        """Test truncating messages after specified index."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            storage = ConversationStorage(temp_conversation_dir)
            session_id = await storage.create_session(assistant_id="default")

            # Add multiple messages
            await storage.append_message(session_id, "user", "Message 1")
            await storage.append_message(session_id, "assistant", "Response 1")
            await storage.append_message(session_id, "user", "Message 2")
            await storage.append_message(session_id, "assistant", "Response 2")

            # Truncate after index 1 (keep first 2 messages)
            await storage.truncate_messages_after(session_id, keep_until_index=1)

            # Verify
            session = await storage.get_session(session_id)
            assert len(session["state"]["messages"]) == 2
            assert session["state"]["messages"][0]["content"] == "Message 1"
            assert session["state"]["messages"][1]["content"] == "Response 1"
            assert session["state"]["current_step"] == 1

    @pytest.mark.asyncio
    async def test_truncate_all_messages(self, temp_conversation_dir, mock_assistant_service):
        """Test truncating all messages (keep_until_index=-1)."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            storage = ConversationStorage(temp_conversation_dir)
            session_id = await storage.create_session(assistant_id="default")

            await storage.append_message(session_id, "user", "Message 1")
            await storage.append_message(session_id, "assistant", "Response 1")

            # Truncate all
            await storage.truncate_messages_after(session_id, keep_until_index=-1)

            session = await storage.get_session(session_id)
            assert len(session["state"]["messages"]) == 0
            assert session["state"]["current_step"] == 0

    @pytest.mark.asyncio
    async def test_delete_message(self, temp_conversation_dir, mock_assistant_service):
        """Test deleting a specific message."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            storage = ConversationStorage(temp_conversation_dir)
            session_id = await storage.create_session(assistant_id="default")

            await storage.append_message(session_id, "user", "Message 1")
            await storage.append_message(session_id, "assistant", "Response 1")
            await storage.append_message(session_id, "user", "Message 2")

            # Delete the assistant message (index 1)
            await storage.delete_message(session_id, message_index=1)

            session = await storage.get_session(session_id)
            assert len(session["state"]["messages"]) == 2
            assert session["state"]["messages"][0]["content"] == "Message 1"
            assert session["state"]["messages"][1]["content"] == "Message 2"
            assert session["state"]["current_step"] == 0  # No assistant messages left

    @pytest.mark.asyncio
    async def test_delete_message_out_of_range(self, temp_conversation_dir, mock_assistant_service):
        """Test deleting message with invalid index."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            storage = ConversationStorage(temp_conversation_dir)
            session_id = await storage.create_session(assistant_id="default")

            await storage.append_message(session_id, "user", "Message 1")

            # Try to delete non-existent message
            with pytest.raises(IndexError):
                await storage.delete_message(session_id, message_index=5)

    @pytest.mark.asyncio
    async def test_delete_session(self, temp_conversation_dir, mock_assistant_service):
        """Test deleting a session."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            storage = ConversationStorage(temp_conversation_dir)
            session_id = await storage.create_session(assistant_id="default")

            # Verify file exists
            files_before = list((temp_conversation_dir / "chat").glob("*.md"))
            assert len(files_before) == 1

            # Delete session
            await storage.delete_session(session_id)

            # Verify file is gone
            files_after = list((temp_conversation_dir / "chat").glob("*.md"))
            assert len(files_after) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self, temp_conversation_dir):
        """Test deleting a session that doesn't exist."""
        storage = ConversationStorage(temp_conversation_dir)

        with pytest.raises(FileNotFoundError):
            await storage.delete_session("nonexistent-session-id")

    @pytest.mark.asyncio
    async def test_move_session_moves_compare_sidecar(self, temp_conversation_dir, mock_assistant_service):
        """Test moving a session also moves its compare sidecar file."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            project_root = temp_conversation_dir / "project_roots" / "proj-1"
            project_root.mkdir(parents=True, exist_ok=True)
            storage = ConversationStorage(
                temp_conversation_dir,
                project_root_resolver=lambda project_id: str(project_root) if project_id == "proj-1" else None,
            )
            session_id = await storage.create_session(assistant_id="default")

            source_path = await storage._find_session_file(session_id)
            assert source_path is not None
            source_compare_path = source_path.with_suffix(".compare.json")
            compare_payload = '{"msg-1": {"responses": [{"model_id": "deepseek:deepseek-chat", "model_name": "DeepSeek Chat", "content": "hello"}]}}'
            source_compare_path.write_text(compare_payload, encoding='utf-8')

            await storage.move_session(
                session_id,
                source_context_type="chat",
                target_context_type="project",
                target_project_id="proj-1",
            )

            moved_path = await storage._find_session_file(session_id, context_type="project", project_id="proj-1")
            assert moved_path is not None
            moved_compare_path = moved_path.with_suffix(".compare.json")

            assert not source_path.exists()
            assert not source_compare_path.exists()
            assert moved_compare_path.exists()
            assert moved_compare_path.read_text(encoding='utf-8') == compare_payload

    @pytest.mark.asyncio
    async def test_copy_session_copies_compare_sidecar(self, temp_conversation_dir, mock_assistant_service):
        """Test copying a session also copies its compare sidecar file."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            project_root = temp_conversation_dir / "project_roots" / "proj-2"
            project_root.mkdir(parents=True, exist_ok=True)
            storage = ConversationStorage(
                temp_conversation_dir,
                project_root_resolver=lambda project_id: str(project_root) if project_id == "proj-2" else None,
            )
            session_id = await storage.create_session(assistant_id="default")

            source_path = await storage._find_session_file(session_id)
            assert source_path is not None
            source_compare_path = source_path.with_suffix(".compare.json")
            compare_payload = '{"msg-1": {"responses": [{"model_id": "openai:gpt-4", "model_name": "GPT-4", "content": "hi"}]}}'
            source_compare_path.write_text(compare_payload, encoding='utf-8')

            copied_session_id = await storage.copy_session(
                session_id,
                source_context_type="chat",
                target_context_type="project",
                target_project_id="proj-2",
            )

            copied_path = await storage._find_session_file(copied_session_id, context_type="project", project_id="proj-2")
            assert copied_path is not None
            copied_compare_path = copied_path.with_suffix(".compare.json")

            assert source_compare_path.exists()
            assert copied_compare_path.exists()
            assert copied_compare_path.read_text(encoding='utf-8') == compare_payload

    @pytest.mark.asyncio
    async def test_cleanup_temporary_sessions_deletes_compare_sidecar(self, temp_conversation_dir):
        """Test cleanup removes compare sidecars of temporary sessions."""
        storage = ConversationStorage(temp_conversation_dir)

        chat_dir = temp_conversation_dir / "chat"
        chat_dir.mkdir(parents=True, exist_ok=True)
        session_path = chat_dir / "2026-01-01_12345678.md"
        import frontmatter
        temp_post = frontmatter.Post("## User\nhello")
        temp_post.metadata = {"session_id": "test-session", "temporary": True}
        session_path.write_text(frontmatter.dumps(temp_post), encoding='utf-8')

        compare_path = session_path.with_suffix(".compare.json")
        compare_path.write_text('{"msg-1": {"responses": []}}', encoding='utf-8')

        cleaned = await storage.cleanup_temporary_sessions()

        assert cleaned == 1
        assert not session_path.exists()
        assert not compare_path.exists()

    @pytest.mark.asyncio
    async def test_update_session_model(self, temp_conversation_dir):
        """Test updating session's model."""
        # Create mock assistant
        default_assistant = Mock()
        default_assistant.id = "default"
        default_assistant.model_id = "deepseek:deepseek-chat"

        mock_service = AsyncMock()
        mock_service.get_default_assistant.return_value = default_assistant
        mock_service.get_assistant.return_value = default_assistant

        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_service):
            storage = ConversationStorage(temp_conversation_dir)
            session_id = await storage.create_session(assistant_id="default")

            # Update model
            await storage.update_session_model(session_id, "openai:gpt-4")

            # Verify - read file directly since get_session may override model_id
            import frontmatter
            filepath = await storage._find_session_file(session_id)
            with open(filepath, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)

            assert post.metadata["model_id"] == "openai:gpt-4"

    @pytest.mark.asyncio
    async def test_update_session_assistant(self, temp_conversation_dir, mock_assistant_service):
        """Test updating session's assistant."""
        with patch('src.api.services.assistant_config_service.AssistantConfigService', return_value=mock_assistant_service):
            # Mock different assistant
            new_assistant = AsyncMock()
            new_assistant.id = "coding-expert"
            new_assistant.model_id = "deepseek:deepseek-coder"
            mock_assistant_service.get_assistant.return_value = new_assistant

            storage = ConversationStorage(temp_conversation_dir)
            session_id = await storage.create_session(assistant_id="default")

            # Update assistant
            await storage.update_session_assistant(session_id, "coding-expert")

            # Verify
            session = await storage.get_session(session_id)
            assert session["assistant_id"] == "coding-expert"
            assert session["model_id"] == "deepseek:deepseek-coder"

    @pytest.mark.asyncio
    async def test_parse_messages_with_usage(self, temp_conversation_dir):
        """Test parsing messages from markdown content."""
        storage = ConversationStorage(temp_conversation_dir)

        markdown_content = """
## User (2026-01-25 14:30:15)
What is Python?

## Assistant (2026-01-25 14:30:22)
Python is a programming language.

<!-- usage: {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30} -->
<!-- cost: {"total_cost": 0.0015, "currency": "USD"} -->
"""

        messages = storage._parse_messages(markdown_content, session_id="test-session")

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "What is Python?"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Python is a programming language."
        assert "usage" in messages[1]
        assert messages[1]["usage"]["total_tokens"] == 30
        assert "cost" in messages[1]
        assert messages[1]["cost"]["total_cost"] == 0.0015
