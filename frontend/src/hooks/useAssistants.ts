/**
 * Assistant management Hook
 *
 * Manages assistant configuration state and operations
 */

import { useState, useCallback, useEffect } from 'react';
import type { Assistant, AssistantCreate, AssistantUpdate } from '../types/assistant';
import * as api from '../services/api';

export function useAssistants() {
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [defaultAssistantId, setDefaultAssistantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load all assistants
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [assistantsData, defaultId] = await Promise.all([
        api.listAssistants(),
        api.getDefaultAssistantId(),
      ]);
      setAssistants(assistantsData);
      setDefaultAssistantId(defaultId);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load assistants';
      setError(message);
      console.error('Failed to load assistants:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // ==================== Assistant Operations ====================

  const createAssistant = useCallback(async (assistant: AssistantCreate) => {
    try {
      await api.createAssistant(assistant);
      await loadData(); // Reload data
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create assistant';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const updateAssistant = useCallback(async (assistantId: string, assistant: AssistantUpdate) => {
    try {
      await api.updateAssistant(assistantId, assistant);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update assistant';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const deleteAssistant = useCallback(async (assistantId: string) => {
    try {
      await api.deleteAssistant(assistantId);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete assistant';
      setError(message);
      throw err;
    }
  }, [loadData]);

  // ==================== Default Assistant ====================

  const setDefaultAssistant = useCallback(async (assistantId: string) => {
    try {
      await api.setDefaultAssistant(assistantId);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to set default assistant';
      setError(message);
      throw err;
    }
  }, [loadData]);

  return {
    // State
    assistants,
    defaultAssistantId,
    loading,
    error,

    // Operations
    createAssistant,
    updateAssistant,
    deleteAssistant,
    setDefaultAssistant,
    refreshData: loadData,
  };
}
