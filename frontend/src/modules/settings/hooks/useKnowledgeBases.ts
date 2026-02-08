/**
 * Knowledge base management hook
 *
 * Manages knowledge base configuration state and operations
 */

import { useState, useCallback, useEffect } from 'react';
import type { KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate } from '../../../types/knowledgeBase';
import * as api from '../../../services/api';

export function useKnowledgeBases() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load all knowledge bases
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listKnowledgeBases();
      setKnowledgeBases(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load knowledge bases';
      setError(message);
      console.error('Failed to load knowledge bases:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadData();
  }, [loadData]);

  const createKnowledgeBase = useCallback(async (kb: KnowledgeBaseCreate) => {
    try {
      await api.createKnowledgeBase(kb);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create knowledge base';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const updateKnowledgeBase = useCallback(async (kbId: string, kb: KnowledgeBaseUpdate) => {
    try {
      await api.updateKnowledgeBase(kbId, kb);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update knowledge base';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const deleteKnowledgeBase = useCallback(async (kbId: string) => {
    try {
      await api.deleteKnowledgeBase(kbId);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete knowledge base';
      setError(message);
      throw err;
    }
  }, [loadData]);

  return {
    knowledgeBases,
    loading,
    error,
    createKnowledgeBase,
    updateKnowledgeBase,
    deleteKnowledgeBase,
    refreshData: loadData,
  };
}
