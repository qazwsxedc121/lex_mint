<!-- Generated: 2026-02-17 (Updated) | Files scanned: ~80 | Token estimate: ~850 -->

# Frontend Architecture

## Entry Point
`frontend/src/main.tsx` -> `App.tsx` (React Router v7)

## Route Tree
```
/ -> redirect to /chat
/chat/:sessionId?       -> ChatModule
/projects/:projectId?   -> ProjectsModule
/settings/*             -> SettingsModule (14 sub-routes)
/developer              -> DeveloperModule
```

## Component Hierarchy

```
<MainLayout>
  <GlobalSidebar />           # App-level nav (Chat, Projects, Settings, Developer)
  <Outlet>
    ChatModule
      ChatSidebar             # Session list, folders, drag-and-drop
        FolderList > DroppableFolderHeader > DraggableSession
      ChatView                # Main chat interface
        Header (AssistantSelector, ParamOverridePopover, CompareModelButton)
        ContextUsageBar
        MessageList > MessageBubble (ReactMarkdown, CodeBlock, ThinkingBlock, MermaidBlock)
        FollowupChips
        InputBox (TextArea, FilePickerPopover, AttachmentList, SendButton)

    ProjectsModule
      ProjectSidebar > FileTree (recursive TreeNode)
      ProjectWorkspace (Tabs, CodeMirror editor, ChatPanel)

    SettingsModule
      SettingsSidebar
      CrudPagesFactory -> Table + Modal (assistants, models, providers, knowledge-bases, prompt-templates)
      ConfigForm (title-generation, followup, compression, translation, tts, etc.)
      PromptTemplatesPage (config-driven CRUD with variable schema editor)

  <CommandPalette />          # Global overlay (Cmd+K)
</MainLayout>
```

## Key Components (by size)

| Component | Lines | Purpose |
|-----------|-------|---------|
| InputBox.tsx | 2,009 | Message input, attachments, file picker |
| MessageBubble.tsx | 1,230 | Message rendering, markdown, code blocks, actions |
| ChatSidebar.tsx | 837 | Session list, folders, drag-drop, search |
| ParamOverridePopover.tsx | 429 | Model parameter controls |
| ChatView.tsx | 290 | Main chat interface orchestration |
| CrudPagesFactory.tsx | ~300 | Generic CRUD page generator for settings |

## State Management

| Mechanism | Scope | Usage |
|-----------|-------|-------|
| Zustand | Global | `projectWorkspaceStore.ts` - project state |
| React Context | Module | `ChatServiceProvider` (API DI), `ChatComposerContext` (input state) |
| Custom Hooks | Feature | `useChat`, `useSessions`, `useFolders`, `useTTS` |
| URL State | Route | Session ID, project ID via React Router params |

## Shared Components
`frontend/src/shared/chat/` (6,909 lines) - Reusable chat UI used by both Chat and Projects modules:
- `components/` (20 components) - MessageBubble, InputBox, CodeBlock, etc.
- `hooks/` - useChat, useSessions, useFolders
- `services/` - defaultChatAPI.ts (Axios + SSE)
- `contexts/` - ChatServiceProvider

## i18n
- Library: react-i18next
- Namespaces: common, chat, settings, projects
- Languages: en (fallback), zh-CN
- Files: `frontend/src/i18n/locales/{lang}/{namespace}.json`

## Build & Dev
- Vite 7.2.4, TypeScript 5.9.3, Tailwind CSS 4
- Dev server: http://localhost:5173
- API proxy configured to backend port
