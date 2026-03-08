import { useMemo } from 'react';
import { useProjectWorkspaceStore } from '../../../stores/projectWorkspaceStore';
import type { ProjectWorkspaceTab } from '../workspace';
import { getProjectWorkspacePath } from '../workspace';

export interface ProjectHomeSummary {
  recentFilePath: string | null;
  recentFileName: string | null;
  recentSessionId: string | null;
  recentTab: ProjectWorkspaceTab;
  recentTabPath: string;
  continueEditingPath: string;
  hasWorkContext: boolean;
  chatSidebarOpen: boolean;
  fileTreeOpen: boolean;
}

const getFileName = (filePath: string | null | undefined): string | null => {
  if (!filePath) {
    return null;
  }

  const normalized = filePath.replace(/\\/g, '/');
  const parts = normalized.split('/').filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : normalized;
};

export function useProjectHomeSummary(projectId: string): ProjectHomeSummary {
  const projectFileMap = useProjectWorkspaceStore((state) => state.projectFileMap);
  const projectSessionMap = useProjectWorkspaceStore((state) => state.projectSessionMap);
  const projectTabMap = useProjectWorkspaceStore((state) => state.projectTabMap);
  const chatSidebarOpen = useProjectWorkspaceStore((state) => state.chatSidebarOpen);
  const fileTreeOpen = useProjectWorkspaceStore((state) => state.fileTreeOpen);

  return useMemo(() => {
    const recentTab = projectTabMap[projectId] || 'project';
    const recentFilePath = projectFileMap[projectId] || null;
    const recentSessionId = projectSessionMap[projectId] || null;
    const continueEditingTab: ProjectWorkspaceTab = recentFilePath ? 'files' : recentTab === 'project' ? 'files' : recentTab;

    return {
      recentFilePath,
      recentFileName: getFileName(recentFilePath),
      recentSessionId,
      recentTab,
      recentTabPath: getProjectWorkspacePath(projectId, recentTab),
      continueEditingPath: getProjectWorkspacePath(projectId, continueEditingTab),
      hasWorkContext: Boolean(recentFilePath || recentSessionId || recentTab !== 'project'),
      chatSidebarOpen,
      fileTreeOpen,
    };
  }, [chatSidebarOpen, fileTreeOpen, projectFileMap, projectId, projectSessionMap, projectTabMap]);
}
