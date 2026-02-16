<!-- Generated: 2026-02-17 (Updated) | Files scanned: ~25 | Token estimate: ~550 -->

# Data Architecture

## Storage Strategy: No Traditional Database

All data stored as files - human-readable, Git-friendly, sync-friendly.

## Conversation Storage (Markdown)

**Format:** `.md` with YAML frontmatter
**Location:** `conversations/chat/` (chat), `{project}/.lex_mint/conversations/` (projects)
**Naming:** `YYYY-MM-DD_HH-MM-SS_{session_id[:8]}.md`

```markdown
---
session_id: uuid-string
assistant_id: general-assistant
model_id: deepseek:deepseek-chat
created_at: 2026-02-17T10:30:00
title: Session Title
current_step: 5
temporary: false
total_usage: {prompt_tokens: 1200, completion_tokens: 800}
total_cost: 0.0042
---

## User (2026-02-17 10:30:15)
Message content...

## Assistant (2026-02-17 10:30:22)
Response content...
```

**Concurrency:** Per-file asyncio locks in ConversationStorage

## Vector Storage (ChromaDB)

**Location:** `data/chromadb/`
**Collections:**
- Knowledge base vectors (one collection per KB)
- Memory vectors (global + per-assistant)

**Embedding:** Local GGUF models via llama-cpp-python, or provider embeddings

## Configuration (YAML)

**Two-tier system:**
```
config/
  defaults/     # Immutable defaults (in git)
  local/        # Runtime state (gitignored)
```

**Key configs:**
- `models_config.yaml` - Providers, models, pricing, capabilities
- `assistants_config.yaml` - Assistant definitions, system prompts
- `keys_config.yaml` - API keys (gitignored)
- `chat_folders.yaml` - Folder structure
- Feature configs: compression, rag, translation, tts, search, webpage, followup, title-generation, file-reference

## Runtime State

- `data/state/` - JSON/YAML files for runtime state (e.g. `prompt_templates_config.yaml`)
- `attachments/{session_id}/{message_index}/` - File attachments
- `logs/server.log` - Backend logs
