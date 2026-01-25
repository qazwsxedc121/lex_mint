# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LangGraph-based AI agent system using DeepSeek as the LLM provider. The codebase demonstrates basic agent patterns including state management, node-based processing, and conditional routing.

## Development Environment

**Primary Platform**: Windows

All commands and examples in this document are provided for Windows unless otherwise noted. When providing commands, always default to Windows syntax (e.g., `venv\Scripts\activate` for virtual environment activation).

## Development Commands

### Setup
```bash
# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running
```bash
# Run the main agent
python -m src.main
```

### Testing
```bash
# Run all tests
pytest

# Run single test file
pytest tests/unit/test_simple_agent.py

# Run single test function
pytest tests/unit/test_simple_agent.py::test_chat_node

# Run with coverage
pytest --cov=src --cov-report=html
```

### Code Quality
```bash
# Linting
ruff check .

# Format code
ruff format .

# Type checking
mypy .

# Run all checks
ruff check . && ruff format --check . && mypy .
```

## Architecture

### LangGraph Pattern
The agent system uses LangGraph's state-based architecture:
- **State**: Defined with `TypedDict` in `src/state/`, uses `Annotated[List, add]` for message accumulation
- **Nodes**: Pure functions in `src/agents/` that take state and return state updates (partial updates only)
- **Graph**: Built with `StateGraph`, compiled before use
- **Routing**: Uses `add_conditional_edges` with routing functions that return string keys

### Key Implementation Details
1. **DeepSeek Integration**: Uses DeepSeek API (not standard OpenAI), requires `DEEPSEEK_API_KEY` env var
   - Base URL: `https://api.deepseek.com`
   - Model: `deepseek-chat`
   - Configured in `ChatOpenAI` with custom `base_url`

2. **Message Format**: State stores messages as dicts with `role` and `content` keys, then converts to LangChain message objects (HumanMessage/AIMessage) for LLM invocation

3. **State Updates**: Node functions return partial state updates as dicts - LangGraph merges them using the type annotations (e.g., `add` operator for message lists)

4. **Entry Point**: `src/main.py` loads `.env` before importing agents (critical for API key access)

### File Structure
```
src/
├── agents/           # Agent graph definitions and node functions
├── state/            # TypedDict state definitions with Annotated types
├── utils/            # Helper functions
└── main.py           # Entry point (loads .env, runs CLI loop)
tests/
└── unit/             # Unit tests with mocked LLM calls
```

## Testing Patterns

- Mock `ChatOpenAI` class in tests using `patch('src.agents.simple_agent.ChatOpenAI')`
- Mock response object needs `.content` attribute for message content
- Test node functions independently before testing full graph
- State type hints enable better test coverage

## Environment Variables

Required `.env` file:
```
DEEPSEEK_API_KEY=your_key_here
```

Optional for LangSmith tracing:
```
LANGCHAIN_API_KEY=your_key_here
LANGCHAIN_TRACING_V2=true
```
