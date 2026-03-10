# Backend Module Responsibilities and Structure Guide

## Purpose

This document defines the target responsibility boundaries for the backend modules.
It is a guidance document for future refactors, not a claim that the current codebase
already matches this structure exactly.

The goal is to answer three questions clearly:

1. Which module owns which kind of logic?
2. Where should new files go?
3. Which current cross-layer patterns should be reduced over time?


## Current Diagnosis

The backend is already partially layered, but the boundaries are not yet stable.

The main symptoms are:

- `src/api/services/` currently mixes transport-adjacent services, application orchestration,
  storage access, runtime composition, and some infrastructure behavior.
- `src/agents/` is moving toward LLM runtime ownership, but the directory name still suggests
  only "agent objects" rather than runtime execution.
- A normal chat request currently crosses too many thin intermediate layers, which makes the
  main path harder to reason about.
- Some names are historical and still show up in older docs and tests.

This means the codebase is not unstructured, but it does not yet express one consistent
architecture vocabulary.


## Current Status Snapshot

- API entry now resolves `ChatApplicationService` directly
- production bootstrap now comes from `src/application/chat/`
- workflow execution now resolves from `src/application/workflows/`
- legacy `AgentService` has been removed
- legacy `simple_llm.py` has been removed
- runtime code is centered in `src/agents/llm_runtime/`
- infrastructure storage package now lives under `src/infrastructure/storage/` (with compatibility shims)
- file infrastructure package now lives under `src/infrastructure/files/` (with compatibility shims)
- config infrastructure package now lives under `src/infrastructure/config/` (with compatibility shims, including model config)
- web infrastructure package now lives under `src/infrastructure/web/` (with compatibility shims)
- `src/api/services/` still contains many transitional modules, but some chat application
  ownership has already moved into `src/application/chat/`


## Core Principles

### 1. One layer, one reason to change

Each layer should have a primary change driver:

- API layer changes because HTTP contracts or streaming protocols change.
- Application layer changes because product behavior or use cases change.
- LLM runtime changes because model invocation behavior changes.
- Provider layer changes because external model SDKs or provider-specific quirks change.
- Infrastructure changes because persistence or external system integration changes.

### 2. Direction of dependency should be stable

Preferred flow:

`api -> application -> llm_runtime -> providers`

Supporting services such as storage, retrieval, and file access should be injected into
the application layer or runtime layer as dependencies. Lower layers should not import
HTTP router logic or FastAPI request models.

### 3. "Service" is not enough to describe ownership

`services/` is acceptable as a transitional directory, but it must not remain a generic
dumping ground. Each service should still belong to a clear conceptual layer.

### 4. Runtime code and business orchestration are different concerns

These must stay separate:

- Business orchestration: when to compress, when to search, how to persist, what to emit
- Runtime execution: how to stream chunks, how to trim context, how to resolve reasoning,
  how to run tool loops, how to adapt to provider SDKs


## Target Module Responsibilities

### `src/api/`

Owns transport and API-facing concerns only.

Should contain:

- FastAPI app bootstrap
- routers
- request/response models that exist for HTTP contracts
- dependency wiring for HTTP entrypoints
- HTTP-specific error mapping
- SSE / flow event transport protocol mapping

Should not contain:

- model runtime logic
- provider adapter logic
- deep chat orchestration rules
- storage implementation details

Examples:

- `src/api/routers/chat.py`
- `src/api/dependencies.py`
- `src/api/models/*`


### Application Layer

Target ownership: product use cases and orchestration.

Short-term transitional location:

- `src/api/services/`

Long-term preferred location:

- `src/application/`

Owns:

- single chat flow
- group chat flow
- compare flow
- workflow execution flow
- context preparation coordination
- post-turn persistence orchestration
- feature-level policy decisions

Should contain:

- use-case orchestration
- coordination between storage, context assembly, tools, runtime, and post-processing
- behavior decisions like auto-compression triggers

Should not contain:

- provider SDK details
- chunk streaming internals
- direct runtime protocol logic when it can live in `llm_runtime`
- FastAPI-specific request handling

Examples in current codebase:

- `src/application/chat/service.py`
- `src/application/chat/bootstrap.py`
- `src/application/chat/group_chat_service.py`
- `src/application/chat/single_chat_flow_service.py`
- `src/application/chat/compare_flow_service.py`
- `src/application/chat/context_assembly_service.py`
- `src/application/chat/post_turn_service.py`
- `src/application/workflows/execution_service.py`
- transitional compatibility shims in `src/api/services/chat_application_service.py`
- transitional compatibility shims in `src/api/services/single_chat_flow_service.py`
- transitional compatibility shims in `src/api/services/compare_flow_service.py`
- transitional compatibility shims in `src/api/services/workflow_execution_service.py`


### `src/agents/` (current meaning: LLM runtime and agent execution)

Current recommended ownership:

- LLM runtime
- tool loop runtime
- stream call policy
- context shaping immediately before model invocation
- multimodal message conversion
- reasoning/thinking runtime decisions

This directory is no longer just "agents" in the narrow sense.
Today it is effectively the LLM execution/runtime layer.

Short-term rule:

- Keep model runtime logic here.

Long-term naming option:

- Consider renaming this layer to `src/llm_runtime/` if the repo continues in this direction.

Should contain:

- code that turns an already-prepared chat request into a provider invocation
- stream execution loops
- tool round management
- model-call parameter resolution

Should not contain:

- session persistence
- project/file CRUD orchestration
- HTTP transport logic
- feature-level decisions about when a use case should call the model

Examples:

- `src/agents/llm_runtime/*`
- `src/agents/tool_loop_runner.py`
- `src/agents/stream_call_policy.py`


### `src/providers/`

Owns provider abstraction and external model integration.

Should contain:

- adapter interfaces
- adapter registry
- provider capability normalization
- provider-specific request/response handling
- SDK integration details

Should not contain:

- business use-case orchestration
- session logic
- HTTP route concerns

Examples:

- `src/providers/registry.py`
- `src/providers/types.py`
- `src/providers/adapters/*`


### `src/tools/`

Owns tool definitions and tool registry, not chat orchestration.

Should contain:

- tool schemas
- tool registration
- builtin tools
- request-scoped tool entrypoints

Should not contain:

- tool loop policy
- general chat flow orchestration

Examples:

- `src/tools/definitions.py`
- `src/tools/registry.py`
- `src/tools/request_scoped.py`


### Infrastructure Concerns

The codebase already has infrastructure behavior, but it is not fully isolated as a layer yet.

These concerns include:

- conversation storage
- file access
- project file tree access
- vector store access
- external web fetching
- config repository access

Many of these currently live in `src/api/services/`.
That is acceptable during transition, but they should be treated as infrastructure-oriented services,
not as part of the transport layer.

Examples:

- `conversation_storage.py`
- `file_service.py`
- `project_service.py`
- `webpage_service.py`
- `model_config_service.py`


### `src/state/`

Owns shared runtime state shapes only.

Should contain:

- typed runtime state definitions
- reusable state containers used across runtime/orchestration flows

Should not contain:

- business logic
- transport logic
- provider SDK logic


### `src/utils/`

Owns small, generic helpers only.

Should contain:

- logging helpers
- pure formatting helpers
- tiny utilities with no domain ownership

Should not contain:

- business orchestration
- provider-specific logic
- large subsystems hidden behind a generic name


## Target Call Chain for a Normal Chat

The preferred single-chat path should read like this:

1. API router accepts request and validates transport contract
2. Application service prepares use-case inputs
3. Application service assembles context and resolves tools
4. LLM runtime executes one model turn
5. Provider adapter talks to external model API
6. Application service persists outputs and emits follow-up events
7. API layer maps results to HTTP or SSE payloads

In short:

`router -> application -> llm_runtime -> provider adapter`

This is the target conceptual flow even if some current code still contains transitional wrappers.


## Target File Structure Guidance

This is the preferred direction for backend structure:

```text
src/
  api/
    main.py
    dependencies.py
    routers/
    models/
    errors.py
    logging_config.py

  application/
    chat/
    group_chat/
    compare/
    workflows/
    context/
    post_turn/

  agents/
    llm_runtime/
    tool_loop_runner.py
    stream_call_policy.py

  providers/
    adapters/
    registry.py
    types.py
    base.py

  tools/
    builtin/
    registry.py
    definitions.py
    request_scoped.py

  infrastructure/
    storage/
    files/
    retrieval/
    config/

  state/
  utils/
```

Notes:

- `application/` and `infrastructure/` are target-state concepts. They do not need to be
  created all at once.
- During transition, files may temporarily remain under `src/api/services/`, but new code should
  still follow the target ownership model.


## Placement Rules for New Code

When adding a new file, use these rules:

### Put it in `src/api/` if:

- it defines an HTTP route
- it maps HTTP payloads to internal calls
- it defines API request/response schemas
- it handles SSE transport formatting

### Put it in the application layer if:

- it coordinates a use case from start to finish
- it decides when to call compression/search/memory/rag/runtime
- it persists outputs after a runtime completes
- it emits business-level events

### Put it in `src/agents/` if:

- it changes how a model turn is executed
- it shapes prompt/runtime context right before invocation
- it manages streaming details
- it manages tool loop rounds or reasoning runtime behavior

### Put it in `src/providers/` if:

- it exists because one provider behaves differently from another
- it talks directly to provider SDKs or APIs
- it normalizes provider capabilities or stream chunks

### Put it in infrastructure-oriented modules if:

- it reads or writes files
- it stores or loads sessions
- it accesses vector stores or databases
- it wraps external services that are not themselves LLM providers


## Boundaries That Need Special Discipline

### Chat Application Entry

The production API path now resolves `ChatApplicationService` directly.

This is the intended direction:

- API routes should depend on application entry services directly
- API dependency composition should import from `src/application/...` instead of bouncing
  through legacy `src/api/services/...` files
- compatibility facades should be removed once tests and old callers migrate
- application composition should live in explicit bootstrap/factory modules instead of a
  generic god service

### `src/api/services/`

This directory is transitional.
Its contents should gradually be classified into:

- application orchestration
- infrastructure support
- legacy compatibility

It should not be treated as a permanent architecture concept.

### Compatibility exports

Temporary compatibility should prefer package-level re-exports over whole legacy files.
When callers are migrated, the old filenames should be removed instead of kept alive indefinitely.
The current chat package split already follows this pattern for the main chat application entry.


## Non-Goals

This document does not define:

- the exact migration sequence
- file-by-file move order
- naming of every future package
- test migration details

Those belong in the refactor plan.


## Decision Summary

The backend should be understood in four main layers:

- `src/api/`: transport
- application layer: use-case orchestration
- `src/agents/`: LLM runtime execution
- `src/providers/`: provider integration

Infrastructure behavior exists today but is not yet cleanly isolated.
Future refactors should make that layer more explicit instead of letting `src/api/services/`
continue to absorb unrelated responsibilities.


## Status of This Document

This document is the architecture guidance baseline for the next backend refactor plan.
If a future change conflicts with this document, either:

- update the code to match the guide, or
- revise the guide explicitly before adding more code
