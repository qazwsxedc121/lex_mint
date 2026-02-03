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

  // Map of projectId -> filePath for each project's last opened file
  projectFileMap: Record<string, string>;

  // Map of projectId -> sessionId for each project's last session
  projectSessionMap: Record<string, string>;

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
  toggleChatSidebar: () => void;
  setChatSidebarOpen: (open: boolean) => void;
  toggleFileTree: () => void;
  setFileTreeOpen: (open: boolean) => void;
  clearWorkspace: () => void;
}

export const useProjectWorkspaceStore = create<ProjectWorkspaceState>()(
  persist(
    (set, get) => ({
      currentProjectId: null,
      projectFileMap: {},
      projectSessionMap: {},
      chatSidebarOpen: false,
      fileTreeOpen: true,

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
        currentProjectId: null,
        projectFileMap: {},
        projectSessionMap: {},
        chatSidebarOpen: false,
        fileTreeOpen: true
      }),
    }),
    {
      name: 'project-workspace-storage', // localStorage key
      version: 1, // Increment this to force clear old incompatible data
      migrate: (persistedState: any, version: number) => {
        // If old version or no version, return fresh state
        if (version < 1) {
          return {
            currentProjectId: null,
            projectFileMap: {},
            projectSessionMap: {},
            chatSidebarOpen: false,
            fileTreeOpen: true,
          };
        }
        return persistedState;
      },
    }
  )
);
