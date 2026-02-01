/**
 * Project Workspace Store - Maintains current opened project and file state
 *
 * This store preserves the user's workspace context when switching between modules,
 * ensuring that when they return to the projects page, their previously opened
 * project and file are still active.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ProjectWorkspaceState {
  // Current opened project ID
  currentProjectId: string | null;

  // Current opened file path within the project
  currentFilePath: string | null;

  // Map of projectId -> sessionId for each project's last session
  projectSessionMap: Record<string, string>;

  // Chat sidebar visibility state
  chatSidebarOpen: boolean;

  // Actions to update workspace state
  setCurrentProject: (projectId: string | null) => void;
  setCurrentFile: (filePath: string | null) => void;
  setProjectSession: (projectId: string, sessionId: string | null) => void;
  getProjectSession: (projectId: string) => string | null;
  toggleChatSidebar: () => void;
  setChatSidebarOpen: (open: boolean) => void;
  clearWorkspace: () => void;
}

export const useProjectWorkspaceStore = create<ProjectWorkspaceState>()(
  persist(
    (set, get) => ({
      currentProjectId: null,
      currentFilePath: null,
      projectSessionMap: {},
      chatSidebarOpen: false,

      setCurrentProject: (projectId) => set({
        currentProjectId: projectId,
        // Clear file when switching projects (session is preserved in map)
        currentFilePath: null
      }),

      setCurrentFile: (filePath) => set({
        currentFilePath: filePath
      }),

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

      toggleChatSidebar: () => set((state) => ({
        chatSidebarOpen: !state.chatSidebarOpen
      })),

      setChatSidebarOpen: (open) => set({
        chatSidebarOpen: open
      }),

      clearWorkspace: () => set({
        currentProjectId: null,
        currentFilePath: null,
        projectSessionMap: {},
        chatSidebarOpen: false
      }),
    }),
    {
      name: 'project-workspace-storage', // localStorage key
    }
  )
);
