/**
 * Project management Hook
 *
 * Manages project configuration state and operations
 */

import { useState, useCallback, useEffect } from 'react';
import type { Project, ProjectCreate, ProjectUpdate } from '../../../types/project';
import * as api from '../../../services/api';

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load all projects
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const projectsData = await api.listProjects();
      setProjects(projectsData);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load projects';
      setError(message);
      console.error('Failed to load projects:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // ==================== Project Operations ====================

  const createProject = useCallback(async (project: ProjectCreate) => {
    try {
      await api.createProject(project);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create project';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const updateProject = useCallback(async (projectId: string, project: ProjectUpdate) => {
    try {
      await api.updateProject(projectId, project);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update project';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const deleteProject = useCallback(async (projectId: string) => {
    try {
      await api.deleteProject(projectId);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete project';
      setError(message);
      throw err;
    }
  }, [loadData]);

  return {
    // State
    projects,
    loading,
    error,

    // Operations
    createProject,
    updateProject,
    deleteProject,
    refreshProjects: loadData,
  };
}
