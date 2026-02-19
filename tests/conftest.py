"""Shared pytest fixtures for all tests."""

import pytest
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock


def _create_workspace_temp_dir(kind: str) -> Path:
    """Create a temporary directory under repository-local .pytest_work."""
    repo_root = Path(__file__).resolve().parents[1]
    root_dir = repo_root / ".pytest_work" / kind
    root_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = root_dir / f"{kind}_{uuid.uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


@pytest.fixture
def tmp_path():
    """Workspace-local replacement for pytest's tmp_path fixture."""
    temp_dir = _create_workspace_temp_dir("tmp_path")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_conversation_dir():
    """Create temporary directory for conversation files."""
    temp_dir = _create_workspace_temp_dir("conversations")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_config_dir():
    """Create temporary directory for config files."""
    temp_dir = _create_workspace_temp_dir("config")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_llm_response():
    """Mock LLM response object."""
    mock = Mock()
    mock.content = "This is a test response from the AI assistant."
    return mock


@pytest.fixture
def mock_streaming_llm_response():
    """Mock streaming LLM response chunks."""
    async def async_generator():
        test_chunks = [
            "Hello", " this", " is", " a", " test", " response"
        ]
        for chunk in test_chunks:
            mock_chunk = Mock()
            mock_chunk.content = chunk
            yield mock_chunk

    return async_generator()


@pytest.fixture
def sample_messages():
    """Sample message list for testing."""
    return [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a high-level programming language."},
        {"role": "user", "content": "What are its main features?"}
    ]


@pytest.fixture
def sample_model_config():
    """Sample model configuration for testing."""
    return {
        "default": {
            "provider": "deepseek",
            "model": "deepseek-chat"
        },
        "providers": [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "type": "builtin",
                "protocol": "openai",
                "base_url": "https://api.deepseek.com",
                "enabled": True,
                "sdk_class": "deepseek"
            }
        ],
        "models": [
            {
                "id": "deepseek-chat",
                "name": "DeepSeek Chat",
                "provider_id": "deepseek",
                "tags": ["chat"],
                "enabled": True
            }
        ]
    }


@pytest.fixture
def sample_assistant_config():
    """Sample assistant configuration for testing."""
    return {
        "assistants": [
            {
                "id": "default",
                "name": "Default Assistant",
                "description": "General purpose assistant",
                "system_prompt": "You are a helpful AI assistant.",
                "model_id": "deepseek:deepseek-chat",
                "temperature": 0.7,
                "max_rounds": -1
            }
        ]
    }


@pytest.fixture
def mock_assistant_service():
    """Mock AssistantConfigService."""
    mock = AsyncMock()

    # Mock default assistant
    default_assistant = Mock()
    default_assistant.id = "default"
    default_assistant.name = "Default Assistant"
    default_assistant.model_id = "deepseek:deepseek-chat"
    default_assistant.system_prompt = "You are a helpful AI assistant."
    default_assistant.temperature = 0.7
    default_assistant.max_rounds = -1

    mock.get_default_assistant.return_value = default_assistant
    mock.get_assistant.return_value = default_assistant

    return mock
