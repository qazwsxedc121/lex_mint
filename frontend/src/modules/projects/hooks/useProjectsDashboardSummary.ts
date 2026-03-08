import { useMemo } from 'react';
import { useProjectWorkspaceStore } from '../../../stores/projectWorkspaceStore';
import type { Project } from '../../../types/project';
import type { ProjectWorkspaceTab } from '../workspace';
import { getProjectWorkspacePath } from '../workspace';

export interface ProjectDashboardItem {
  project: Project;
  isCurrent: boolean;
  lastFilePath: string | null;
  lastFileName: string | null;
  lastSessionId: string | null;
  lastTab: ProjectWorkspaceTab;
  openPath: string;
}

export interface ProjectsDashboardSummary {
  recentProject: ProjectDashboardItem | null;
  otherProjects: ProjectDashboardItem[];
  totalProjects: number;
}

const getFileName = (filePath: string | null | undefined): string | null => {
  if (!filePath) {
    return null;
  }

  const normalized = filePath.replace(/\\/g, '/');
  const parts = normalized.split('/').filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : normalized;
};

export function useProjectsDashboardSummary(projects: Project[]): ProjectsDashboardSummary {
  const currentProjectId = useProjectWorkspaceStore((state) => state.currentProjectId);
  const projectFileMap = useProjectWorkspaceStore((state) => state.projectFileMap);
  const projectSessionMap = useProjectWorkspaceStore((state) => state.projectSessionMap);
  const projectTabMap = useProjectWorkspaceStore((state) => state.projectTabMap);

  return useMemo(() => {
    const items = projects.map<ProjectDashboardItem>((project) => {
      const lastTab = projectTabMap[project.id] || 'project';
      const lastFilePath = projectFileMap[project.id] || null;

      return {
        project,
        isCurrent: project.id === currentProjectId,
        lastFilePath,
        lastFileName: getFileName(lastFilePath),
        lastSessionId: projectSessionMap[project.id] || null,
        lastTab,
        openPath: getProjectWorkspacePath(project.id, lastTab),
      };
    });

    const sorted = [...items].sort((a, b) => {
      if (a.isCurrent) {
        return -1;
      }
      if (b.isCurrent) {
        return 1;
      }
      return a.project.name.localeCompare(b.project.name);
    });

    return {
      recentProject: sorted[0] || null,
      otherProjects: sorted.slice(1),
      totalProjects: sorted.length,
    };
  }, [currentProjectId, projectFileMap, projectSessionMap, projectTabMap, projects]);
}
