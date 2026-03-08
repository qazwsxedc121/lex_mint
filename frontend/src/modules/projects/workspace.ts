import type { Project } from '../../types/project';

export type ProjectWorkspaceTab = 'project' | 'files' | 'search' | 'workflows' | 'agent';

export interface ProjectAgentContextItem {
  id: string;
  title: string;
  content: string;
  kind?: 'context' | 'note';
  language?: string;
  source?: {
    filePath: string;
    startLine: number;
    endLine: number;
  };
  origin: 'file' | 'search' | 'workflow';
  createdAt: number;
}

export interface ProjectWorkflowLaunchContext {
  source: 'file-viewer';
  filePath?: string;
  selectedText?: string;
  selectionStart?: number;
  selectionEnd?: number;
}

export interface ProjectsOutletContext {
  projects: Project[];
  projectsLoading?: boolean;
  onManageClick: () => void;
  onAddProjectClick: () => void;
}

export interface ProjectWorkspaceOutletContext extends ProjectsOutletContext {
  projectId: string;
  currentProject?: Project;
  onCloseProject: () => void;
}

export const PROJECT_WORKSPACE_TABS: ProjectWorkspaceTab[] = ['project', 'files', 'search', 'workflows', 'agent'];

export const isProjectWorkspaceTab = (value: string | null | undefined): value is ProjectWorkspaceTab => {
  return value === 'project' || value === 'files' || value === 'search' || value === 'workflows' || value === 'agent';
};

export const getProjectWorkspacePath = (projectId: string, tab: ProjectWorkspaceTab): string => {
  return `/projects/${projectId}/${tab}`;
};
