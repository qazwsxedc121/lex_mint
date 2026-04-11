# API Endpoints (Current)

Last updated: 2026-03-15

This file is a quick map of backend HTTP APIs. The runtime source of truth is:
- Swagger: `/docs`
- OpenAPI JSON: `/openapi.json`
- Routers: `src/api/routers/*.py`

## Health and Runtime

- `GET /api/health` - health probe
- `GET /` - API root (or packaged frontend when enabled)

## Chat and Streaming

- `POST /api/chat` - non-stream chat response
- `POST /api/chat/stream` - chat SSE stream (`flow_event` envelope)
- `POST /api/chat/stream/resume` - replay/resume by `stream_id + last_event_id`
- `POST /api/chat/compare` - multi-model compare SSE stream
- `POST /api/chat/compress` - context compression SSE stream
- `POST /api/chat/upload` - upload chat attachment
- `GET /api/chat/attachment/{session_id}/{message_index}/{filename}` - attachment download
- `DELETE /api/chat/message` - delete one message
- `PUT /api/chat/message` - edit one message
- `POST /api/chat/separator` - insert separator
- `POST /api/chat/clear` - clear one session

### SSE protocol notes

- Stream payload is canonical `{"flow_event": {...}}` only.
- Unknown upstream event types are fail-fast: server emits `stream_error` then terminates.
- Legacy passthrough event compatibility is removed.

Protocol doc: `docs/flow_event_protocol_v1.md`

## Sessions and Sidebar Organization

- `POST /api/sessions` - create session
- `GET /api/sessions` - list sessions
- `GET /api/sessions/search` - search sessions
- `GET /api/sessions/{session_id}` - get session detail
- `DELETE /api/sessions/{session_id}` - delete session
- `PUT /api/sessions/{session_id}/target` - switch target (`assistant` or `model`)
- `PUT /api/sessions/{session_id}/assistant` - switch assistant target
- `PUT /api/sessions/{session_id}/model` - switch model target
- `PUT /api/sessions/{session_id}/title` - rename
- `PUT /api/sessions/{session_id}/param-overrides` - update runtime overrides
- `PUT /api/sessions/{session_id}/folder` - assign folder
- `POST /api/sessions/{session_id}/branch` - branch session
- `POST /api/sessions/{session_id}/duplicate` - duplicate session
- `POST /api/sessions/{session_id}/move` - move session between contexts
- `POST /api/sessions/{session_id}/copy` - copy session between contexts
- `POST /api/sessions/{session_id}/save` - persist temporary session
- `GET /api/sessions/{session_id}/export` - export session (`format=markdown|json|...`)
- `POST /api/sessions/import/chatgpt` - import ChatGPT export
- `POST /api/sessions/import/markdown` - import markdown sessions
- `PUT /api/sessions/{session_id}/group-assistants` - set group participants
- `GET /api/sessions/{session_id}/group-settings` - get group settings
- `PUT /api/sessions/{session_id}/group-settings` - update group settings

## Folders

- `GET /api/folders`
- `POST /api/folders`
- `PUT /api/folders/{folder_id}`
- `PATCH /api/folders/{folder_id}/order`
- `DELETE /api/folders/{folder_id}`

## Models and Assistants

### Models / Providers (`/api/models`)

- Builtin provider metadata and profiles
- Provider CRUD and connection tests
- Provider model discovery (`/providers/{provider_id}/fetch-models`)
- Model catalog CRUD (`/list`)
- Default model config (`/default`)
- Capabilities and protocol introspection

### Assistants (`/api/assistants`)

- Assistant CRUD
- Default assistant read/update

## Projects

- Project CRUD
- Workspace root browsing
- Project file/directory CRUD and rename/search
- Project workspace-state APIs
- `POST /api/projects/{project_id}/chat/apply-diff`

## Knowledge / Memory / Prompts

- Knowledge base CRUD and document ingestion/reprocess/chunk inspection
- Memory settings + memory CRUD + semantic search
- Prompt template CRUD

## Feature Config Endpoints

- `GET/PUT /api/rag/config`
- `GET/PUT /api/search/config`
- `GET/PUT /api/webpage/config`
- `GET/PUT /api/compression/config`
- `GET/PUT /api/file-reference/config`
- `GET/PUT /api/translation/config`
- `GET/PUT /api/tts/config`
- `GET/PUT /api/title-generation/config`
- `GET/PUT /api/followup/config`

## Workflows and Async Runs

- Workflows CRUD
- Workflow streaming run: `POST /api/workflows/{workflow_id}/run/stream`
- Workflow async runs: create/list/detail
- Generic async run APIs:
  - `POST /api/runs`
  - `GET /api/runs`
  - `GET /api/runs/{run_id}`
  - `POST /api/runs/{run_id}/cancel`
  - `POST /api/runs/{run_id}/resume` (optional body `{ "checkpoint_id": "..." }`)
  - `GET /api/runs/{run_id}/stream`
  - `POST /api/runs/{run_id}/stream/resume`
- Runtime resume/checkpoint notes:
  - Workflow async execution persists orchestration checkpoints.
  - Resume without `checkpoint_id` uses the latest known checkpoint for that run.
  - Stream payload keeps canonical `flow_event` envelope; workflow events may include `payload.checkpoint_id`.

## Tools

- `GET /api/tools/catalog`

## Features

- `GET /api/features/plugins` - feature plugin statuses
- `GET /api/features/session-export/formats` - available session export formats
