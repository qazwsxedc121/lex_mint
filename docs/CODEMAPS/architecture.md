<!-- Updated: 2026-03-11 | Post backend ownership refactor -->

# Architecture

## System Type
Monorepo: FastAPI backend + React frontend.

## High-Level Data Flow
```
Browser (React + Vite)
  |  SSE streaming / REST
  v
FastAPI (src/api/main.py)
  |  router -> dependency wiring
  v
Application layer (src/application/*)
  |  use-case orchestration
  +---> LLM runtime (src/llm_runtime/*) ---> Provider adapters (src/providers/adapters/*) ---> LLM APIs
  +---> Infrastructure services (src/infrastructure/*) ---> Markdown/YAML/Vector storage + external services
```

## Service Boundaries

| Layer | Location | Responsibility |
|---|---|---|
| API transport | `src/api/` | HTTP contracts, router mapping, SSE transport |
| Application | `src/application/` | Product use-case orchestration |
| Runtime | `src/llm_runtime/` | Model-turn execution, tool loop, stream shaping |
| Providers | `src/providers/` | Provider abstraction and adapter integration |
| Infrastructure | `src/infrastructure/` | Persistence, config, retrieval, knowledge, web, project services |
| Shared core/domain | `src/core/`, `src/domain/models/` | Shared settings/paths/errors and domain models |

## Key Design Decisions

- Legacy transport-adjacent catch-all package was removed (`src/api/services/`).
- Runtime ownership is explicit under `src/llm_runtime/` (legacy `src/agents/` removed).
- Shared config/path helpers moved to `src/core/`; shared models moved to `src/domain/models/`.
- Unit tests mirror ownership (`tests/unit/application`, `tests/unit/infrastructure`, `tests/unit/llm_runtime`, `tests/unit/providers`, `tests/unit/api`, etc.).
- Conversations remain markdown-first and config remains YAML-first for local-first workflows.
