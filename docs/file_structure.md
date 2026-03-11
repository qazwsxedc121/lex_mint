# Project File Structure

This document summarizes the current repository structure and ownership boundaries.

## Directory Overview

```
lex_mint/
├── src/                    # Backend Python code
├── frontend/               # Frontend React application
├── tests/                  # Backend tests (pytest)
├── docs/                   # Architecture and feature docs
├── config/                 # Runtime and defaults YAML config
├── conversations/          # Conversation markdown storage
├── attachments/            # Uploaded files
└── logs/                   # Runtime logs
```

## Backend Structure (`src/`)

### API Transport (`src/api/`)

- `main.py` - FastAPI app bootstrap
- `dependencies.py` - API dependency wiring
- `routers/` - HTTP + SSE route handlers
- `errors.py` - API-layer error mapping
- `logging_config.py` - logging setup

### Core Shared Modules

- `src/core/` - shared paths, settings, and cross-layer helpers
- `src/domain/models/` - shared Pydantic domain models

### Application Layer (`src/application/`)

- `chat/` - single/group/compare chat orchestration
- `flow/` - flow event mapping and async run orchestration
- `tools/` - tool-catalog orchestration for use cases
- `translation/` - translation use-case orchestration
- `workflows/` - workflow execution orchestration

### Runtime + Provider Layer

- `src/llm_runtime/` - model-turn runtime execution, tool loop, streaming, reasoning
- `src/providers/` - provider registry + adapters
- `src/providers/adapters/` - provider-specific protocol adapters

### Infrastructure Layer (`src/infrastructure/`)

- `storage/` - conversation and async-run persistence
- `files/` - file IO services
- `config/` - YAML-backed configuration services
- `retrieval/` - retrieval, embedding, rerank, sqlite-vec
- `knowledge/` - knowledge base and document processing
- `web/` - search and webpage services
- `memory/` - memory services
- `compression/` - compression services/config
- `projects/` - project-scoped infrastructure helpers
- `llm/` - local LLM helper services
- `audio/` - TTS services

### Supporting Modules

- `src/tools/` - builtin + request-scoped tool definitions/registry
- `src/state/` - shared runtime state models
- `src/evals/` - evaluation scripts/helpers
- `src/utils/` - generic utilities
- `src/main.py` - backend CLI entrypoint

## Frontend Structure (`frontend/src/`)

- `main.tsx` - frontend entrypoint
- `App.tsx` - route composition
- `modules/chat/` - chat UI and flow
- `modules/settings/` - settings screens
- `modules/projects/` - project UI
- `services/api.ts` - API client
- `types/` - frontend type definitions

## Testing Structure (`tests/`)

- `tests/api/` - API-level integration tests
- `tests/integration/` - integration and port behavior tests
- `tests/unit/application/` - application-layer unit tests
- `tests/unit/infrastructure/` - infrastructure-layer unit tests
- `tests/unit/llm_runtime/` - runtime unit tests
- `tests/unit/providers/` - provider unit tests
- `tests/unit/api/` - router/dependency unit tests
- `tests/unit/domain/`, `tests/unit/core/`, `tests/unit/tools/`, `tests/unit/evals/`, `tests/unit/cross_layer/`

## Key Architectural Patterns

### Backend

1. Layered ownership: `api -> application -> llm_runtime/providers` + `infrastructure`
2. Provider adapter pattern for multi-provider LLM support
3. Markdown + YAML config/data persistence (no mandatory DB)
4. SSE event transport with flow-event mapping

### Frontend

1. Vite + React module-oriented feature structure
2. Zustand state stores for feature state
3. Tailwind CSS styling system
4. TypeScript-first contracts with backend API

## Key Files by Purpose

| Purpose | Location |
|---|---|
| API routes | `src/api/routers/` |
| Chat orchestration | `src/application/chat/` |
| Runtime execution | `src/llm_runtime/` |
| Provider integration | `src/providers/adapters/` |
| Config services | `src/infrastructure/config/` |
| Conversation persistence | `src/infrastructure/storage/conversation_storage.py` |
| Shared domain models | `src/domain/models/` |
| Frontend feature UI | `frontend/src/modules/` |
