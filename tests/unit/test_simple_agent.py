"""Unit tests for simple agent."""

import pytest
from unittest.mock import Mock, patch
from src.agents.simple_agent import create_simple_agent, chat_node
from src.state.agent_state import SimpleAgentState


@pytest.fixture
def mock_llm_response():
    """Mock LLM response."""
    mock = Mock()
    mock.content = "Hello! This is a test response."
    return mock


def test_chat_node(mock_llm_response):
    """Test the chat node function."""
    state: SimpleAgentState = {
        "messages": [{"role": "user", "content": "Hello"}],
        "current_step": 0
    }
    
    with patch('src.agents.simple_agent.ChatOpenAI') as mock_llm:
        mock_llm.return_value.invoke.return_value = mock_llm_response
        
        result = chat_node(state)
        
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "assistant"
        assert result["messages"][0]["content"] == "Hello! This is a test response."
        assert result["current_step"] == 1


def test_create_simple_agent():
    """Test agent creation."""
    agent = create_simple_agent()
    
    assert agent is not None
    assert hasattr(agent, 'invoke')


def test_should_continue_logic():
    """Test the conditional routing logic."""
    from src.agents.simple_agent import should_continue
    
    state_continue: SimpleAgentState = {
        "messages": [],
        "current_step": 5
    }
    assert should_continue(state_continue) == "continue"
    
    state_end: SimpleAgentState = {
        "messages": [],
        "current_step": 10
    }
    assert should_continue(state_end) == "end"
