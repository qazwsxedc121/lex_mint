# Backend Architecture Map

Last updated: 2026-03-13

This map tracks the current backend module boundaries after legacy compatibility removal.

## Entry and Wiring

- App entry: `src/api/main.py`
- Router registration: `src/api/routers/*.py`
- Error handlers: `src/api/errors.py`
- Chat graph bootstrap: `src/application/chat/bootstrap.py`

## Layer Overview

- `src/api/` - HTTP/SSE transport, request validation, response shaping
- `src/application/` - use-case orchestration and flow event mapping
- `src/infrastructure/` - config persistence, storage, providers, retrieval, files, web
- `src/domain/` - shared data models and enums
- `src/providers/` - provider adapters and registry

## Chat Path (Canonical)

1. `POST /api/chat/stream` enters `src/api/routers/chat.py`
2. Router delegates to `ChatApplicationService` from `src/application/chat/service.py`
3. Single-turn path runs `SingleChatFlowService`
4. Group path runs `GroupChatService` with orchestrators from `src/application/chat/orchestration/`
5. Compare path runs `CompareFlowService` + `CompareModelsOrchestrator`
6. Stream output is normalized by flow event mappers and sent as SSE

## Orchestration Modes

Current group orchestration modes:
- `round_robin`
- `committee`
- `compare_models`

Removed:
- `single_turn` orchestration compatibility branch

## Flow Event Contract

Source of truth:
- Event types: `src/application/flow/flow_event_types.py`
- Mapper: `src/application/flow/flow_event_mapper.py`

Policy:
- canonical `flow_event` envelope only
- unknown upstream event types -> `stream_error` + immediate terminate
- no legacy passthrough event fallback

See `docs/flow_event_protocol_v1.md`.

## API Domain Routers

- Chat: `chat.py`, `translation.py`
- Sessions and folders: `sessions.py`, `folders.py`
- Models and assistants: `models.py`, `assistants.py`
- Knowledge and memory: `knowledge_base.py`, `memory.py`
- Projects: `projects.py`
- Workflows and async runs: `workflows.py`, `runs.py`
- Feature configs: `rag_config.py`, `compression_config.py`, `search_config.py`, `webpage_config.py`, `file_reference_config.py`, `translation_config.py`, `tts_config.py`, `title_generation.py`, `followup.py`
- Prompt templates/tools: `prompt_templates.py`, `tools.py`

## High-Impact Services

- Conversation storage: `src/infrastructure/storage/conversation_storage.py`
- Model/provider config: `src/infrastructure/config/model_config_service.py`
- Assistant config: `src/infrastructure/config/assistant_config_service.py`
- RAG config/service: `src/infrastructure/config/rag_config_service.py`, `src/infrastructure/knowledge/rag_service.py`
- Memory service: `src/infrastructure/memory/memory_service.py`
- Project service: `src/infrastructure/config/project_service.py`

## Runtime Notes

- Resume/replay stream API lives in both chat and async run routers.
- Session target is canonicalized by `target_type` + `assistant_id/model_id`.
- Legacy session/config compatibility paths are removed.
