/**
 * File Tree Hook
 *
 * Manages file tree state for a project
 */

import { useState, useCallback, useEffect } from 'react';
import type { FileNode } from '../../../types/project';
import * as api from '../../../services/api';

export function useFileTree(projectId: string | null) {
  const [tree, setTree] = useState<FileNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load file tree
  const loadTree = useCallback(async () => {
    if (!projectId) {
      setTree(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const treeData = await api.getFileTree(projectId);
      setTree(treeData);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load file tree';
      setError(message);
      console.error('Failed to load file tree:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Load on mount and when projectId changes
  useEffect(() => {
    loadTree();
  }, [loadTree]);

  return {
    tree,
    loading,
    error,
    refreshTree: loadTree,
  };
}
