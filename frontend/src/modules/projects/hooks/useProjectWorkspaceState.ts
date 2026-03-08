import { useCallback, useEffect, useMemo, useState } from 'react';
import { getProjectWorkspaceState, type ProjectWorkspaceState } from '../../../services/api';

export function useProjectWorkspaceState(projectId: string) {
  const [workspaceState, setWorkspaceState] = useState<ProjectWorkspaceState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadWorkspaceState = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getProjectWorkspaceState(projectId);
      setWorkspaceState(data);
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to load project workspace state';
      setError(String(message));
      setWorkspaceState(null);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void loadWorkspaceState();
  }, [loadWorkspaceState]);

  return useMemo(() => ({
    workspaceState,
    loading,
    error,
    refresh: loadWorkspaceState,
  }), [error, loadWorkspaceState, loading, workspaceState]);
}
