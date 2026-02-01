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

  // Actions to update workspace state
  setCurrentProject: (projectId: string | null) => void;
  setCurrentFile: (filePath: string | null) => void;
  clearWorkspace: () => void;
}

export const useProjectWorkspaceStore = create<ProjectWorkspaceState>()(
  persist(
    (set) => ({
      currentProjectId: null,
      currentFilePath: null,

      setCurrentProject: (projectId) => set({
        currentProjectId: projectId,
        // Clear file when switching projects
        currentFilePath: null
      }),

      setCurrentFile: (filePath) => set({
        currentFilePath: filePath
      }),

      clearWorkspace: () => set({
        currentProjectId: null,
        currentFilePath: null
      }),
    }),
    {
      name: 'project-workspace-storage', // localStorage key
    }
  )
);
