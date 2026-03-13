# Data Architecture

Last updated: 2026-03-13

## Storage Model

No relational database is required for core runtime paths.
Data is persisted in markdown/yaml/json files plus vector storage.

## Core Data Locations

Resolved under `user_data_root()` from `src/core/paths.py`.
By default:
- dev runtime: repository root
- packaged runtime: user app-data directory (`~/.lex_mint/app` or platform equivalent)

Primary directories:
- Conversations: `conversations/`
- Attachments: `attachments/`
- Runtime state: `data/state/`
- Logs: `logs/`
- Knowledge assets: `data/knowledge_bases/`

## Conversation Storage

Implementation:
- `src/infrastructure/storage/conversation_storage.py`
- `src/infrastructure/storage/conversation_storage_paths.py`

Format:
- one session per markdown file with yaml frontmatter
- chat context: `conversations/chat/*.md`
- project context: `<project_root>/.lex_mint/conversations/*.md`

Canonical session target metadata:
- `target_type` (`assistant` or `model`)
- `assistant_id` (assistant target only)
- `model_id` (model target, or resolved assistant model)

Compatibility policy:
- legacy pseudo assistant IDs and fallback parsing are removed
- incompatible old metadata is rejected as invalid session input

## Config Layering

Canonical config layout:
- tracked defaults: `config/defaults/*.yaml`
- writable runtime local: `config/local/*.yaml`

Path helpers:
- `config_defaults_dir()`
- `config_local_dir()`
- `resolve_layered_read_path()`
- `ensure_local_file()`

Policy:
- local overrides are preferred when present
- defaults bootstrap local files on first run
- legacy config directory fallback has been removed

## Runtime State Files

`data/state/` stores runtime-managed state, for example:
- workflows config
- prompt templates
- memory settings
- project index/config

## Vector and Retrieval Storage

RAG backend is configured by `RagConfigService`:
- `sqlite_vec` backend (sqlite file)
- `chroma` backend (persist directory)

Knowledge and memory services consume the configured backend through infrastructure services.

## Logging and Observability Data

- App logs: `logs/server.log`
- LLM interaction logs: `logs/llm_interactions_YYYYMMDD.log`

See `docs/LLM_LOGGING.md` for inspection workflow.
