/**
 * File Content Hook
 *
 * Manages file content loading for a specific file
 */

import { useState, useCallback, useEffect } from 'react';
import type { FileContent } from '../../../types/project';
import * as api from '../../../services/api';

export function useFileContent(projectId: string | null, filePath: string | null) {
  const [content, setContent] = useState<FileContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load file content
  const loadContent = useCallback(async () => {
    if (!projectId || !filePath) {
      setContent(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const contentData = await api.readFile(projectId, filePath);
      setContent(contentData);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load file content';
      setError(message);
      console.error('Failed to load file content:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId, filePath]);

  // Load when projectId or filePath changes
  useEffect(() => {
    loadContent();
  }, [loadContent]);

  return {
    content,
    loading,
    error,
    refreshContent: loadContent,
  };
}
