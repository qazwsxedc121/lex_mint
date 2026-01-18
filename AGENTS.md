# AGENTS.md

This file provides guidelines for agentic coding agents working in this repository.

## Project Overview

This project develops AI agents using LangGraph framework. The codebase is organized around modular agent components, state management, and tool integrations.

## Development Commands

### Environment Setup
```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Code Quality
```bash
# Type checking
mypy .

# Linting
ruff check .

# Format code
ruff format .

# Run all checks together
ruff check . && ruff format --check . && mypy .
```

### Testing
```bash
# Run all tests
pytest

# Run single test file
pytest tests/test_module.py

# Run single test function
pytest tests/test_module.py::test_function_name

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run tests in verbose mode
pytest -v
```

### Running the Agent
```bash
# Run main agent
python -m src.main

# Run specific agent module
python -m src.agents.my_agent
```

## Code Style Guidelines

### Imports
- Use `isort` for import organization (handled by ruff)
- Group imports: standard library, third-party, local modules
- Use absolute imports for internal modules
- Avoid wildcard imports (`from module import *`)
- Example:
  ```python
  from typing import Dict, List, Optional
  
  from langgraph.graph import StateGraph
  from langchain_openai import ChatOpenAI
  
  from src.utils.helpers import format_response
  ```

### Type Hints
- Always use type hints for function parameters and return values
- Use `typing` module for complex types: `Dict[str, Any]`, `List[str]`, `Optional[str]`
- Define custom types for complex state structures
- Example:
  ```python
  from typing import TypedDict
  
  class AgentState(TypedDict):
      messages: List[dict]
      context: Dict[str, Any]
      step: int
  
  def process_message(state: AgentState) -> AgentState:
      return state
  ```

### Naming Conventions
- **Variables/Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_prefix_method_name`
- **Agent states**: Descriptive names with `State` suffix (e.g., `ResearchState`, `ChatState`)

### LangGraph Specific Patterns

**State Management**
```python
from langgraph.graph import StateGraph, END

def node_function(state: AgentState) -> Dict[str, Any]:
    # Process state and return updates
    return {"messages": [...], "step": state["step"] + 1}

graph = StateGraph(AgentState)
graph.add_node("process", node_function)
graph.add_edge("process", END)
```

**Conditional Routing**
```python
def should_continue(state: AgentState) -> str:
    if state["step"] >= 5:
        return "end"
    return "continue"

graph.add_conditional_edges("process", should_continue, {
    "continue": "process",
    "end": END
})
```

### Error Handling
- Use specific exception types, avoid bare `except:`
- Log errors with context using `logging` module
- Implement graceful degradation for AI agent failures
- Example:
  ```python
  import logging
  from langchain_core.exceptions import LangChainException
  
  logger = logging.getLogger(__name__)
  
  try:
      response = llm.invoke(prompt)
  except LangChainException as e:
      logger.error(f"LLM invocation failed: {e}", exc_info=True)
      return {"error": str(e), "messages": state["messages"]}
  ```

### File Structure
```
src/
├── agents/           # Agent definitions and graphs
├── tools/            # Custom tools and integrations
├── prompts/          # Prompt templates
├── utils/            # Helper functions
├── state/            # State definitions
└── main.py           # Entry point
tests/
├── unit/             # Unit tests
└── integration/      # Integration tests
```

### Documentation
- Add docstrings to all classes and public functions
- Use Google-style docstrings
- Describe parameters, return values, and exceptions
- Example:
  ```python
  def process_query(query: str, context: Dict[str, Any]) -> str:
      """Process a user query with provided context.
      
      Args:
          query: The user's input query
          context: Additional context information
          
      Returns:
          The processed response string
          
      Raises:
          ValueError: If query is empty
      """
  ```

### Testing Guidelines
- Write unit tests for individual agent nodes
- Write integration tests for complete agent graphs
- Mock external API calls (LLM, databases, etc.)
- Use pytest fixtures for test setup
- Example:
  ```python
  @pytest.fixture
  def mock_llm():
      with patch('src.agents.my_agent.ChatOpenAI') as mock:
          mock.return_value.invoke.return_value = AIMessage(content="test")
          yield mock
  
  def test_agent_node(mock_llm):
      state = {"messages": [HumanMessage(content="test")]}
      result = my_agent_node(state)
      assert "test" in result["messages"][-1].content
  ```

## AI Agent Best Practices

1. **State Design**: Keep state minimal and serializable
2. **Tool Use**: Implement proper error handling and retries for tools
3. **Memory**: Use LangGraph's checkpointing for conversation persistence
4. **Modularity**: Break complex agents into smaller, reusable nodes
5. **Observability**: Add logging at key decision points
6. **Security**: Never hardcode API keys, use environment variables

## Environment Variables

Required variables (create `.env` file):
```
DEEPSEEK_API_KEY=your_key_here
```

Optional variables for LangSmith tracing:
```
LANGCHAIN_API_KEY=your_key_here
LANGCHAIN_TRACING_V2=true
```