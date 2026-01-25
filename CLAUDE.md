# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LangGraph-based AI agent system with web interface using FastAPI backend and React frontend. The system uses DeepSeek as the LLM provider and stores conversations in Markdown format for easy cross-device synchronization.

### Key Features
- **Backend**: FastAPI REST API for agent interactions
- **Frontend**: React + TypeScript web interface
- **Storage**: Markdown files with YAML frontmatter (text-based, sync-friendly)
- **LLM**: DeepSeek chat model via LangChain

## Development Environment

**Primary Platform**: Windows

All commands and examples in this document are provided for Windows unless otherwise noted. When providing commands, always default to Windows syntax (e.g., `venv\Scripts\activate` for virtual environment activation).

## Development Commands

### Setup
```bash
# Activate virtual environment
venv\Scripts\activate

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
```

### Running

**Backend API** (Terminal 1):
```bash
venv\Scripts\activate
uvicorn src.api.main:app --reload --port 8000
```

**Frontend** (Terminal 2):
```bash
cd frontend
npm run dev
```

Access the web interface at http://localhost:5173

**CLI Mode** (original):
```bash
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

### Web Interface Architecture

**Backend (FastAPI)**:
- `src/api/main.py` - FastAPI application entry point
- `src/api/config.py` - Configuration management (pydantic-settings)
- `src/api/routers/` - API endpoints
  - `sessions.py` - Session CRUD operations
  - `chat.py` - Chat message handling
- `src/api/services/` - Business logic
  - `conversation_storage.py` - Markdown file management
  - `agent_service.py` - Agent wrapper for chat processing

**Frontend (React + TypeScript)**:
- `frontend/src/components/` - React components
  - `ChatContainer.tsx` - Main container
  - `MessageList.tsx` - Message display
  - `MessageBubble.tsx` - Individual messages
  - `InputBox.tsx` - Message input
  - `Sidebar.tsx` - Session list
- `frontend/src/hooks/` - Custom React hooks
  - `useChat.ts` - Chat state management
  - `useSessions.ts` - Session list management
- `frontend/src/services/api.ts` - Axios API client
- `frontend/src/types/message.ts` - TypeScript type definitions

**Storage System**:
- Conversations stored in `conversations/` directory
- Format: Markdown files with YAML frontmatter
- Filename: `YYYY-MM-DD_HH-MM-SS_[session_id].md`
- Each file contains:
  - Metadata (session_id, title, created_at, current_step)
  - Timestamped messages in Markdown format
- Supports manual editing and cross-device sync (Dropbox, OneDrive, etc.)

### API Endpoints

- `POST /api/sessions` - Create new conversation session
- `GET /api/sessions` - List all sessions
- `GET /api/sessions/{id}` - Get session details with message history
- `DELETE /api/sessions/{id}` - Delete a session
- `POST /api/chat` - Send message and receive AI response
- `GET /api/health` - Health check

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

5. **Conversation Storage**: Markdown files with frontmatter allow:
   - Human-readable format
   - Easy manual editing
   - Cross-device synchronization
   - Version control friendly
   - No database required

### File Structure
```
src/
├── agents/           # Agent graph definitions and node functions
├── api/              # FastAPI web interface
│   ├── main.py       # FastAPI app entry point
│   ├── config.py     # Configuration management
│   ├── routers/      # API endpoints
│   └── services/     # Business logic (storage, agent wrapper)
├── state/            # TypedDict state definitions with Annotated types
├── utils/            # Helper functions
└── main.py           # CLI entry point (loads .env, runs CLI loop)
frontend/
├── src/
│   ├── components/   # React UI components
│   ├── hooks/        # Custom React hooks
│   ├── services/     # API client
│   └── types/        # TypeScript types
conversations/        # Markdown conversation files
tests/
└── unit/             # Unit tests with mocked LLM calls
```

## Conversation File Format

Example: `conversations/2026-01-25_14-30-00_abc12345.md`

```markdown
---
session_id: 550e8400-e29b-41d4-a716-446655440000
created_at: 2026-01-25T14:30:00
title: Python性能优化讨论
current_step: 2
---

## User (2026-01-25 14:30:15)
如何优化Python代码性能？

## Assistant (2026-01-25 14:30:22)
Python性能优化有几个常用方法...
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

Optional for API configuration:
```
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173
CONVERSATIONS_DIR=conversations
LOG_LEVEL=INFO
```

Optional for LangSmith tracing:
```
LANGCHAIN_API_KEY=your_key_here
LANGCHAIN_TRACING_V2=true
```

Frontend `.env` (optional):
```
VITE_API_URL=http://localhost:8000
```
