<!-- Generated: 2026-02-17 (Updated) | Files scanned: ~290 | Token estimate: ~750 -->

# Architecture

## System Type
Monorepo: FastAPI backend + React 19 frontend, LangGraph AI agent system

## High-Level Data Flow
```
Browser (React 19 + Vite)
  |  SSE streaming / REST
  v
FastAPI (src/api/main.py)
  |  20 routers
  v
Service Layer (37 services)
  |
  +---> Provider Adapters (5) ---> LLM APIs (DeepSeek, OpenAI, Anthropic, Ollama, XAI)
  +---> ConversationStorage  ---> Markdown files (conversations/)
  +---> ChromaDB             ---> Vector embeddings (data/chromadb/)
  +---> YAML configs         ---> config/local/*.yaml
```

## Service Boundaries

| Layer | Location | Responsibility |
|-------|----------|----------------|
| API Routers | `src/api/routers/` (20 files) | HTTP handling, request validation |
| Services | `src/api/services/` (37 files) | Business logic, orchestration |
| Models | `src/api/models/` (6 files) | Pydantic request/response schemas |
| Providers | `src/providers/` | LLM abstraction, adapter pattern |
| Agents | `src/agents/` | LangGraph workflow, streaming LLM calls |
| Storage | `conversations/`, `config/`, `data/` | Markdown files, YAML configs, ChromaDB |

## Key Design Decisions

- **No database**: Markdown files with YAML frontmatter for conversations (Git/sync-friendly)
- **Provider adapter pattern**: Unified interface across 5 LLM providers
- **Two-tier config**: `config/defaults/` (immutable) + `config/local/` (runtime, gitignored)
- **SSE streaming**: Real-time token streaming from LLM to browser
- **Module-based frontend**: `/modules/chat`, `/modules/settings`, `/modules/projects`
- **Prompt templates**: Reusable templates with JSON variable schema (text/number/boolean/select)
- **RAG reranking**: Model-based reranking via RerankService for improved retrieval
