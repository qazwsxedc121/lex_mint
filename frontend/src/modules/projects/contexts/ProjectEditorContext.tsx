/**
 * ProjectEditorContext - Context for sharing editor actions within Projects module
 *
 * This context allows components (like chat sidebar) to interact with the editor
 * (like inserting content at cursor position) without tight coupling.
 */

import { createContext, useContext } from 'react';

export interface ProjectEditorContextValue {
  /**
   * Insert content at the current cursor position in the editor
   */
  insertToEditor: (content: string) => void;

  /**
   * Whether an editor is currently available and ready
   * (i.e., a file is open and editor is initialized)
   */
  isEditorAvailable: boolean;
}

export const ProjectEditorContext = createContext<ProjectEditorContextValue | null>(null);

/**
 * Hook to access the ProjectEditor context
 * Returns null if used outside Projects module
 */
export const useProjectEditor = () => {
  return useContext(ProjectEditorContext);
};
