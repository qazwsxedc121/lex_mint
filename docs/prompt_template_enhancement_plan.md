# Prompt Template Enhancement Plan

Last updated: 2026-02-10

## Goal

Improve prompt input efficiency in chat compose, and unify reusable prompt templates with common short phrases in one feature set.

Current MVP status (already implemented):
- Searchable template picker in chat toolbar
- Slash trigger (`/`) quick insert in textarea
- Recent + pinned behavior (local browser storage)

This document defines the next phases for future implementation.

## Product Direction

### 1) Unify concepts
Treat both "prompt templates" and "common phrases" as one entity:
- Suggested name: `PromptSnippet`
- Types: `template` and `phrase`

### 2) Keep interaction simple
- Fast insert first
- Optional advanced config
- Backward compatible with current templates

### 3) Delay performance work
Performance tuning is explicitly out of scope for now unless user-visible latency appears.

## Phase 1 - Data Model Upgrade (Backend + Frontend Types)

### Scope
Extend the current template model without breaking existing data.

### Proposed fields
- `id: string`
- `name: string`
- `description?: string`
- `content: string`
- `enabled: boolean`
- `kind: "template" | "phrase"` (default: `template`)
- `trigger?: string` (example: `review`, used by `/review`)
- `aliases?: string[]`
- `tags?: string[]`
- `scope: "global" | "assistant" | "project"` (default: `global`)
- `assistant_id?: string`
- `project_id?: string`
- `insert_mode: "insert" | "replace_selection" | "append"` (default: `insert`)
- `usage_count?: number`
- `last_used_at?: string` (ISO datetime)
- `sort_order?: number`
- `created_at?: string`
- `updated_at?: string`

### Files to update
- `src/api/models/prompt_template.py`
- `src/api/services/prompt_template_service.py`
- `src/api/routers/prompt_templates.py`
- `frontend/src/types/promptTemplate.ts`

### Acceptance criteria
- Old YAML still loads without manual migration
- New fields are optional with safe defaults
- Existing create/update/list flows still work

## Phase 2 - API and Persistence Upgrade

### Scope
Move recent/pinned metadata from browser-only state to server persistence.

### API changes (additive)
- Keep current CRUD endpoints
- Add usage endpoints:
  - `POST /api/prompt-templates/{id}/use`
  - `POST /api/prompt-templates/{id}/pin`
  - `POST /api/prompt-templates/{id}/unpin`
- Add query support on list endpoint:
  - `kind`, `scope`, `assistant_id`, `project_id`, `tag`, `enabled`

### Optional endpoint
- `POST /api/prompt-templates/reorder`

### Acceptance criteria
- Pinned and recent state is shared across sessions/devices
- List endpoint can return scope-filtered templates
- No behavior regression in current UI

## Phase 3 - Compose UX Upgrade

### Scope
Make insert workflows faster and more predictable.

### Planned UX improvements
- Exact slash command first:
  - If input is `/review`, prioritize `trigger == review`
  - Fallback to fuzzy search by name/description/content
- Rich slash rows:
  - Show trigger, tags, and scope badges
- Selection behavior:
  - Respect `insert_mode`
  - Support replacement of highlighted text
- Quick actions:
  - Pin/unpin in slash menu
  - Keyboard shortcut for opening template picker

### Files to update
- `frontend/src/shared/chat/components/InputBox.tsx`

### Acceptance criteria
- Slash insert feels deterministic for exact trigger matches
- Users can apply snippets without leaving keyboard
- Insert behavior is predictable and documented

## Phase 4 - Settings UX Upgrade

### Scope
Improve manageability when template count grows.

### Planned capabilities
- New fields in create/edit form:
  - kind, trigger, tags, scope, insert_mode
- Group views:
  - by kind, by scope, by tags
- Validation rules:
  - unique trigger in same scope
  - reject invalid trigger format
- Bulk operations:
  - enable/disable
  - tag add/remove

### Files to update
- `frontend/src/modules/settings/config/promptTemplates.config.tsx`
- `frontend/src/modules/settings/hooks/usePromptTemplates.ts`
- shared CRUD form config if new field types are needed

### Acceptance criteria
- Power users can organize 50+ snippets effectively
- Invalid triggers are blocked before submit

## Phase 5 - Variables and Dynamic Templates

### Scope
Add optional variables for reusable structured prompts.

### Template syntax proposal
- `{{topic}}`
- `{{language}}`
- `{{cursor}}` (cursor anchor after insertion)

### UX behavior
- If variables exist, show a lightweight fill dialog before insert
- Preserve current one-click insert for templates without variables

### Safety
- Escape/validate variable values before interpolation

### Acceptance criteria
- Variable templates are usable without slowing simple templates
- Cursor placement works correctly with `{{cursor}}`

## Migration and Compatibility

### Data migration strategy
- Lazy migration on read/write
- Missing fields auto-filled by defaults
- Keep YAML format initially

### Future storage option
- If complex querying grows, evaluate SQLite migration
- Migration only when justified by maintenance cost

## Testing Plan

### Backend
- Unit tests for model defaults and validation
- Service tests for add/update/delete with new fields
- Router tests for filtering and usage endpoints

### Frontend
- Unit tests for:
  - slash matching and ranking
  - insert mode behavior
  - trigger matching priority
- Manual checks:
  - keyboard navigation
  - pin/recent persistence
  - dark mode rendering

## Execution Order (Recommended)

1. Phase 1 (model upgrade, backward compatibility)
2. Phase 2 (server-side recent/pin)
3. Phase 3 (compose UX refinement)
4. Phase 4 (settings management at scale)
5. Phase 5 (variables)

## Risks and Notes

- Keep slash flow lightweight; avoid modal interruptions by default
- Avoid overfitting model early; ship additive fields first
- Defer performance tuning until real latency or scale issues are observed
