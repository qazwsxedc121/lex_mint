import { api } from './apiClient';

import type {
  Project,
  ProjectCreate,
  ProjectToolCatalogResponse,
  ProjectUpdate,
} from '../types/project';

/**
 * Get all projects.
 */
export async function listProjects(): Promise<Project[]> {
  const response = await api.get<Project[]>('/api/projects');
  return response.data;
}

/**
 * Get the unified tool catalog used by project settings and tool-aware UIs.
 */
export async function getToolCatalog(): Promise<ProjectToolCatalogResponse> {
  const response = await api.get<ProjectToolCatalogResponse>('/api/tools/catalog');
  return response.data;
}

/**
 * Create a new project.
 */
export async function createProject(project: ProjectCreate): Promise<Project> {
  const response = await api.post<Project>('/api/projects', project);
  return response.data;
}

/**
 * Get a specific project.
 */
export async function getProject(id: string): Promise<Project> {
  const response = await api.get<Project>(`/api/projects/${id}`);
  return response.data;
}

/**
 * Update a project.
 */
export async function updateProject(id: string, data: ProjectUpdate): Promise<Project> {
  const response = await api.put<Project>(`/api/projects/${id}`, data);
  return response.data;
}

/**
 * Delete a project.
 */
export async function deleteProject(id: string): Promise<void> {
  await api.delete(`/api/projects/${id}`);
}
