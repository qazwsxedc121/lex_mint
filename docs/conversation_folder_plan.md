# Conversation Folder Organization - Implementation Plan

> Created: 2026-02-11
> Status: Phase 1 completed, Phase 2-4 pending

---

## Background

Cherry Studio, LobeHub, ChatGPT etc. all support organizing conversations into folders/groups. Our sidebar currently shows a flat list of sessions, which becomes hard to navigate as conversations accumulate. This plan outlines an incremental approach to add conversation organization capabilities.

---

## Phase 1 - Time-based Grouping (DONE)

**Scope**: Pure frontend change, no backend/storage changes.

**What was done**:
- Added `groupSessionsByTime()` helper to `ChatSidebar.tsx`
- Sessions are grouped into: Today / Yesterday / This Week / This Month / Older
- Groups use `updated_at` (fallback to `created_at`) for classification
- Empty groups are automatically hidden
- Group headers are sticky within the scroll container

**Files changed**:
- `frontend/src/shared/chat/components/ChatSidebar.tsx`

---

## Phase 2 - Custom Folders (Next)

**Goal**: Let users create named folders and move conversations into them.

### 2.1 Backend Changes

**Storage**: Add `folder_id` field to conversation frontmatter:
```yaml
---
session_id: xxx
title: My Chat
folder_id: folder_abc123  # NEW - optional, null = ungrouped
---
```

**New config file** `config/chat_folders.yaml`:
```yaml
folders:
  - id: folder_abc123
    name: Work
    order: 0
    color: blue       # optional accent color
  - id: folder_def456
    name: Learning
    order: 1
    color: green
```

**New API endpoints**:
- `GET /api/folders` - List all folders (ordered)
- `POST /api/folders` - Create folder `{ name, color? }`
- `PUT /api/folders/{id}` - Rename / reorder / recolor
- `DELETE /api/folders/{id}` - Delete folder (sessions become ungrouped)
- `PUT /api/sessions/{id}/folder` - Move session to folder `{ folder_id }` or `null`

**Backend service** (`src/api/services/folder_service.py`):
- CRUD for `chat_folders.yaml`
- Update session frontmatter `folder_id` field via `conversation_storage.py`

### 2.2 Frontend Changes

**Sidebar layout** (within ChatSidebar.tsx or extracted component):
```
[+ New Folder]           <- toolbar button
── Work (3)              <- collapsible folder, click to expand
   ├─ Session A
   ├─ Session B
   └─ Session C
── Learning (2)          <- collapsible folder
   ├─ Session D
   └─ Session E
── Ungrouped             <- sessions with no folder_id (time-grouped as Phase 1)
   ├─ Today
   │  └─ Session F
   └─ This Week
      └─ Session G
```

**Key interactions**:
- Right-click session -> "Move to Folder" submenu
- Folder header click to expand/collapse (state persisted in localStorage)
- Folder context menu: Rename / Delete / Change Color
- Ungrouped sessions still use time-based grouping from Phase 1

### 2.3 Estimated Scope

- Backend: 1 new service + 1 new router + frontmatter field
- Frontend: Folder list component, move-to-folder menu, folder CRUD modal

---

## Phase 3 - Drag & Drop

**Goal**: Drag sessions between folders, drag to reorder folders.

**Dependencies**: Phase 2 complete.

**Approach**:
- Use `@dnd-kit/core` (already popular in React ecosystem, lightweight)
- Draggable session items + droppable folder containers
- Drag session to folder header = move to that folder
- Drag folder headers to reorder
- Visual feedback: highlight drop target, ghost preview

**Scope**: Frontend-only (uses Phase 2 API for persistence).

---

## Phase 4 - Tags (Optional Enhancement)

**Goal**: Allow tagging sessions with multiple labels for cross-cutting organization.

**Why separate from folders**: Folders are exclusive (1 session = 1 folder). Tags are inclusive (1 session = N tags). Both are useful for different mental models.

**Storage**: Add `tags` field to frontmatter:
```yaml
---
session_id: xxx
folder_id: folder_abc
tags: [python, debugging]  # NEW
---
```

**Frontend**: Tag chips in session list items, filter-by-tag in sidebar header.

**Scope**: Medium - backend tag CRUD + frontmatter field + frontend filter UI.

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Frontmatter-based storage (not filesystem folders) | Avoids file moves, compatible with sync tools, one session can have folder + tags |
| YAML config for folder definitions | Consistent with existing config pattern (models, assistants, etc.) |
| Time grouping as Phase 1 | Zero backend changes, immediate UX improvement |
| Folders before tags | More intuitive for most users, simpler mental model |
| `@dnd-kit` for drag-and-drop | Lightweight, accessible, good React integration |

---

## Relationship to Projects

Projects (`context_type=project`) are a **workspace** concept - they group conversations with a code directory and file browser. Folders are a **personal organization** concept within the global chat context.

- Projects: scoped workspace with files + conversations
- Folders: user-defined grouping of global chat conversations
- Both can coexist: project conversations are already separated from global chat
