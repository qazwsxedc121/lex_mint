/**
 * Project Workspace Store - Maintains current opened project and file state
 *
 * This store preserves the user's workspace context when switching between modules,
 * ensuring that when they return to the projects page, their previously opened
 * project and file are still active.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ProjectAgentContextItem, ProjectWorkflowLaunchContext, ProjectWorkspaceTab } from '../modules/projects/workspace';

interface ProjectWorkspaceState {
  // Current opened project ID
  currentProjectId: string | null;

  // Map of projectId -> filePath for each project's last opened file
  projectFileMap: Record<string, string>;

  // Map of projectId -> sessionId for each project's last session
  projectSessionMap: Record<string, string>;

  // Map of projectId -> sessionId for each project's last agent session
  agentSessionMap: Record<string, string>;

  // Map of projectId -> accumulated Agent context items
  agentContextMap: Record<string, ProjectAgentContextItem[]>;

  // One-shot context queue when jumping into project Agent
  pendingAgentContextMap: Record<string, ProjectAgentContextItem[]>;

  // Map of projectId -> last active workspace tab
  projectTabMap: Record<string, ProjectWorkspaceTab>;

  // One-shot launch context when jumping from files into project workflows
  pendingWorkflowLaunchMap: Record<string, ProjectWorkflowLaunchContext>;

  // Chat sidebar visibility state
  chatSidebarOpen: boolean;
  // File tree visibility state
  fileTreeOpen: boolean;

  // Actions to update workspace state
  setCurrentProject: (projectId: string | null) => void;
  setCurrentFile: (projectId: string, filePath: string | null) => void;
  getCurrentFile: (projectId: string) => string | null;
  setProjectSession: (projectId: string, sessionId: string | null) => void;
  getProjectSession: (projectId: string) => string | null;
  setAgentSession: (projectId: string, sessionId: string | null) => void;
  getAgentSession: (projectId: string) => string | null;
  setProjectTab: (projectId: string, tab: ProjectWorkspaceTab) => void;
  getProjectTab: (projectId: string) => ProjectWorkspaceTab;
  addAgentContextItems: (projectId: string, items: ProjectAgentContextItem[]) => void;
  getAgentContextItems: (projectId: string) => ProjectAgentContextItem[];
  consumePendingAgentContext: (projectId: string) => ProjectAgentContextItem[];
  clearAgentContextItems: (projectId: string) => void;
  queueWorkflowLaunch: (projectId: string, context: ProjectWorkflowLaunchContext) => void;
  consumeWorkflowLaunch: (projectId: string) => ProjectWorkflowLaunchContext | null;
  toggleChatSidebar: () => void;
  setChatSidebarOpen: (open: boolean) => void;
  toggleFileTree: () => void;
  setFileTreeOpen: (open: boolean) => void;
  clearWorkspace: () => void;
}

const DEFAULT_WORKSPACE_STATE = {
  currentProjectId: null,
  projectFileMap: {},
  projectSessionMap: {},
  agentSessionMap: {},
  agentContextMap: {},
  pendingAgentContextMap: {},
  projectTabMap: {},
  pendingWorkflowLaunchMap: {},
  chatSidebarOpen: false,
  fileTreeOpen: true,
};

export const useProjectWorkspaceStore = create<ProjectWorkspaceState>()(
  persist(
    (set, get) => ({
      ...DEFAULT_WORKSPACE_STATE,

      setCurrentProject: (projectId) => set({
        currentProjectId: projectId
      }),

      setCurrentFile: (projectId, filePath) => {
        set((state) => {
          const newMap = { ...state.projectFileMap };
          if (filePath === null) {
            delete newMap[projectId];
          } else {
            newMap[projectId] = filePath;
          }
          return { projectFileMap: newMap };
        });
      },

      getCurrentFile: (projectId) => {
        return get().projectFileMap[projectId] || null;
      },

      setProjectSession: (projectId, sessionId) => {
        set((state) => {
          const newMap = { ...state.projectSessionMap };
          if (sessionId === null) {
            delete newMap[projectId];
          } else {
            newMap[projectId] = sessionId;
          }
          return { projectSessionMap: newMap };
        });
      },

      getProjectSession: (projectId) => {
        return get().projectSessionMap[projectId] || null;
      },

      setAgentSession: (projectId, sessionId) => {
        set((state) => {
          const newMap = { ...state.agentSessionMap };
          if (sessionId === null) {
            delete newMap[projectId];
          } else {
            newMap[projectId] = sessionId;
          }
          return { agentSessionMap: newMap };
        });
      },

      getAgentSession: (projectId) => {
        return get().agentSessionMap[projectId] || null;
      },

      setProjectTab: (projectId, tab) => {
        set((state) => ({
          projectTabMap: {
            ...state.projectTabMap,
            [projectId]: tab,
          },
        }));
      },

      getProjectTab: (projectId) => {
        return get().projectTabMap[projectId] || 'project';
      },

      addAgentContextItems: (projectId, items) => {
        if (!items.length) {
          return;
        }

        set((state) => {
          const existing = state.agentContextMap[projectId] || [];
          const merged = [...existing, ...items].slice(-20);
          const pending = [...(state.pendingAgentContextMap[projectId] || []), ...items].slice(-20);

          return {
            agentContextMap: {
              ...state.agentContextMap,
              [projectId]: merged,
            },
            pendingAgentContextMap: {
              ...state.pendingAgentContextMap,
              [projectId]: pending,
            },
          };
        });
      },

      getAgentContextItems: (projectId) => {
        return get().agentContextMap[projectId] || [];
      },

      consumePendingAgentContext: (projectId) => {
        const items = get().pendingAgentContextMap[projectId] || [];
        if (items.length === 0) {
          return [];
        }

        set((state) => {
          const next = { ...state.pendingAgentContextMap };
          delete next[projectId];
          return { pendingAgentContextMap: next };
        });
        return items;
      },

      clearAgentContextItems: (projectId) => {
        set((state) => {
          const nextContext = { ...state.agentContextMap };
          const nextPending = { ...state.pendingAgentContextMap };
          delete nextContext[projectId];
          delete nextPending[projectId];
          return {
            agentContextMap: nextContext,
            pendingAgentContextMap: nextPending,
          };
        });
      },

      queueWorkflowLaunch: (projectId, context) => {
        set((state) => ({
          pendingWorkflowLaunchMap: {
            ...state.pendingWorkflowLaunchMap,
            [projectId]: context,
          },
        }));
      },

      consumeWorkflowLaunch: (projectId) => {
        const context = get().pendingWorkflowLaunchMap[projectId] || null;
        if (!context) {
          return null;
        }
        set((state) => {
          const next = { ...state.pendingWorkflowLaunchMap };
          delete next[projectId];
          return { pendingWorkflowLaunchMap: next };
        });
        return context;
      },

      toggleChatSidebar: () => set((state) => ({
        chatSidebarOpen: !state.chatSidebarOpen
      })),

      setChatSidebarOpen: (open) => set({
        chatSidebarOpen: open
      }),

      toggleFileTree: () => set((state) => ({
        fileTreeOpen: !state.fileTreeOpen
      })),

      setFileTreeOpen: (open) => set({
        fileTreeOpen: open
      }),

      clearWorkspace: () => set({
        ...DEFAULT_WORKSPACE_STATE
      }),
    }),
    {
      name: 'project-workspace-storage', // localStorage key
      version: 3,
      partialize: (state) => ({
        currentProjectId: state.currentProjectId,
        projectFileMap: state.projectFileMap,
        projectSessionMap: state.projectSessionMap,
        agentSessionMap: state.agentSessionMap,
        agentContextMap: state.agentContextMap,
        projectTabMap: state.projectTabMap,
        chatSidebarOpen: state.chatSidebarOpen,
        fileTreeOpen: state.fileTreeOpen,
      }),
      migrate: (persistedState: unknown, version: number) => {
        // If old version or no version, return fresh state
        if (version < 1 || !persistedState || typeof persistedState !== 'object') {
          return { ...DEFAULT_WORKSPACE_STATE };
        }

        const state = persistedState as Partial<ProjectWorkspaceState>;
        return {
          currentProjectId: typeof state.currentProjectId === 'string' ? state.currentProjectId : null,
          projectFileMap: state.projectFileMap ?? {},
          projectSessionMap: state.projectSessionMap ?? {},
          agentSessionMap: state.agentSessionMap ?? {},
          agentContextMap: state.agentContextMap ?? {},
          pendingAgentContextMap: {},
          projectTabMap: state.projectTabMap ?? {},
          pendingWorkflowLaunchMap: {},
          chatSidebarOpen: state.chatSidebarOpen ?? false,
          fileTreeOpen: state.fileTreeOpen ?? true,
        };
      },
    }
  )
);
