# Project File Structure

This document provides a comprehensive overview of the project's file structure and architecture.

## Directory Overview

```
agents-17dcab8b61/
├── src/                    # Backend Python code
├── frontend/               # Frontend React application
├── config/                 # Configuration files (YAML)
├── conversations/          # Conversation storage (Markdown files)
├── logs/                   # Application logs
├── tests/                  # Test files
├── docs/                   # Documentation
└── venv/                   # Python virtual environment
```

## Backend Structure (`src/`)

### API Layer (`src/api/`)

**Core Files:**
- `main.py` - FastAPI application entry point with CORS and router registration
- `config.py` - Pydantic settings configuration management
- `logging_config.py` - Logging system setup

**Data Models (`src/api/models/`):**
- `model_config.py` - Provider, Model, DefaultConfig, ModelsConfig Pydantic models
- `assistant_config.py` - Assistant configuration models

**API Endpoints (`src/api/routers/`):**
- `sessions.py` - Session/conversation CRUD operations
- `chat.py` - Chat message handling with streaming support
- `models.py` - Model management endpoints
- `assistants.py` - Assistant management endpoints

**Business Logic (`src/api/services/`):**
- `conversation_storage.py` - Markdown file-based conversation persistence
- `agent_service.py` - LangGraph-based agent orchestration (legacy)
- `agent_service_simple.py` - Simplified agent service (currently used)
- `model_config_service.py` - Model and provider configuration management
- `assistant_config_service.py` - Assistant configuration management
- `pricing_service.py` - Token usage and cost calculation

### Agent Layer (`src/agents/`)

- `simple_agent.py` - LangGraph state machine with chat node
- `simple_llm.py` - LLM interface with streaming and token tracking

### State Management (`src/state/`)

- `agent_state.py` - TypedDict-based state definitions using `Annotated[List, add]`

### Provider Abstraction (`src/providers/`)

**Core Files:**
- `types.py` - Enums (ApiProtocol, ProviderType), data models (TokenUsage, CostInfo)
- `base.py` - Base provider interface class
- `builtin.py` - Built-in provider registry
- `registry.py` - Provider factory and registry pattern

**Protocol Adapters (`src/providers/adapters/`):**
- `deepseek_adapter.py` - DeepSeek API integration
- `openai_adapter.py` - OpenAI-compatible API integration
- `anthropic_adapter.py` - Anthropic Claude API integration
- `ollama_adapter.py` - Ollama local model integration
- `xai_adapter.py` - XAI (Grok) API integration

### Utilities (`src/utils/`)

- `llm_logger.py` - LLM interaction logging (JSON format, daily rotation)

### Entry Points

- `main.py` - CLI interface for agent interaction

## Frontend Structure (`frontend/src/`)

### Core Files

- `main.tsx` - React application entry point
- `App.tsx` - React Router configuration
- `index.css` - Global styles with Tailwind CSS

### Layouts (`frontend/src/layouts/`)

- `MainLayout.tsx` - Main layout wrapper with nested routing
- `GlobalSidebar.tsx` - Global navigation sidebar

### Feature Modules (`frontend/src/modules/`)

**Chat Module (`modules/chat/`):**
- `index.tsx` - Chat feature router
- `ChatView.tsx` - Main chat interface
- `ChatWelcome.tsx` - Welcome screen for new sessions
- `ChatSidebar.tsx` - Session list and management
- `components/`
  - `MessageBubble.tsx` - Individual message rendering with markdown
  - `MessageList.tsx` - Message list container
  - `InputBox.tsx` - User input field
  - `AssistantSelector.tsx` - Assistant/model selection dropdown
  - `CodeBlock.tsx` - Code syntax highlighting
- `hooks/`
  - `useChat.ts` - Chat state management
  - `useSessions.ts` - Session management logic

**Settings Module (`modules/settings/`):**
- `index.tsx` - Settings router
- `SettingsSidebar.tsx` - Settings navigation tabs
- `AssistantsPage.tsx` - Assistant management UI
- `ModelsPage.tsx` - Model listing and management
- `ProvidersPage.tsx` - Provider configuration
- `components/`
  - `AssistantList.tsx` - Assistant list and editor
  - `ModelList.tsx` - Model management table
  - `ProviderList.tsx` - Provider configuration table
- `hooks/`
  - `useAssistants.ts` - Assistant management logic
  - `useModels.ts` - Model management logic

### Services (`frontend/src/services/`)

- `api.ts` - Axios HTTP client for API communication

### Type Definitions (`frontend/src/types/`)

- `message.ts` - Message interface/type definitions
- `model.ts` - Model and provider type definitions
- `assistant.ts` - Assistant configuration types

### Configuration Files

- `package.json` - Node.js dependencies and scripts
- `tsconfig.json` - TypeScript configuration
- `vite.config.ts` - Vite bundler configuration
- `tailwind.config.js` - Tailwind CSS configuration
- `postcss.config.js` - PostCSS configuration
- `eslint.config.js` - ESLint linting rules

## Configuration (`config/`)

- `models_config.yaml` - LLM providers, models, pricing, capabilities
- `assistants_config.yaml` - Assistant profiles with system prompts
- `keys_config.yaml` - API key management configuration

## Conversation Storage (`conversations/`)

**Format:** `YYYY-MM-DD_HH-MM-SS_[session_id_first_8_chars].md`

**Structure:**
```markdown
---
session_id: uuid
assistant_id: string
model_id: string
created_at: timestamp
title: string
current_step: integer
---

## User (timestamp)
Message content...

## Assistant (timestamp)
Response content...
```

## Testing (`tests/`)

- `unit/test_simple_agent.py` - Agent node unit tests with mocked LLM

## Root Configuration Files

- `pyproject.toml` - Python project metadata, Ruff, MyPy, Pytest config
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (API keys, configuration)
- `CLAUDE.md` - Development guidelines for Claude Code
- `QUICKSTART.txt` - Quick start instructions

## Key Architectural Patterns

### Backend

1. **State Management** - TypedDict with `Annotated[List, add]` for message accumulation
2. **Provider Abstraction** - Multi-provider support via adapter pattern
3. **File-based Storage** - Markdown + YAML frontmatter (no database)
4. **FastAPI** - Async/await with dependency injection

### Frontend

1. **React Router** - Nested routing for modular navigation
2. **Zustand** - State management for chat and settings
3. **Tailwind CSS** - Utility-first CSS framework
4. **TypeScript** - Full type safety throughout

### Storage Strategy

- **Human-readable** - Markdown format for easy editing
- **Sync-friendly** - Works with Dropbox, OneDrive, git
- **No database** - Simple file-based persistence
- **Timestamped** - Complete conversation history

## Key Files by Purpose

| Purpose | Location |
|---------|----------|
| API Endpoints | `src/api/routers/` |
| Business Logic | `src/api/services/` |
| Configuration | `config/` |
| LLM Integration | `src/agents/simple_llm.py`, `src/providers/adapters/` |
| Conversation Storage | `src/api/services/conversation_storage.py` |
| Frontend UI | `frontend/src/modules/` |
| Type Definitions | `frontend/src/types/`, `src/api/models/` |
| State Management | `src/state/` |
