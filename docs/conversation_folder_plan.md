# Conversation Folder Organization

Last updated: 2026-03-13
Status: Implemented (core scope done)

## Current State

Conversation folder organization is implemented across backend + frontend.
The old phased plan is completed for core capabilities.

Implemented capabilities:
- Folder CRUD (`/api/folders`)
- Move session into/out of folder (`PUT /api/sessions/{session_id}/folder`)
- Sidebar folder section with collapse state
- Session drag to folder
- Folder drag reorder
- Context menu move/rename/delete flows

Backend persistence:
- Session markdown frontmatter stores optional `folder_id`
- Folder definitions stored in `config/local/chat_folders.yaml`
- Service: `src/infrastructure/config/folder_service.py`

Frontend entrypoints:
- `frontend/src/shared/chat/components/ChatSidebar.tsx`
- `frontend/src/shared/chat/components/DraggableSession.tsx`
- `frontend/src/shared/chat/components/DroppableFolderHeader.tsx`
- `frontend/src/shared/chat/hooks/useFolders.ts`

## Scope Not Included Yet

The optional tag system (multi-tag per session) is still not implemented.
If needed, it should be tracked as a separate design doc instead of this completed plan.

## Notes

- Folders are a global chat organization concept.
- Project conversations remain scoped under project context and are not replaced by folders.
