/**
 * Prompt template management hook
 */

import { useState, useCallback, useEffect } from 'react';
import type {
  PromptTemplate,
  PromptTemplateCreate,
  PromptTemplateUpdate,
} from '../../../types/promptTemplate';
import * as api from '../../../services/api';

export function usePromptTemplates() {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listPromptTemplates();
      setTemplates(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load prompt templates';
      setError(message);
      console.error('Failed to load prompt templates:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const createTemplate = useCallback(async (template: PromptTemplateCreate) => {
    try {
      await api.createPromptTemplate(template);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create prompt template';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const updateTemplate = useCallback(async (templateId: string, template: PromptTemplateUpdate) => {
    try {
      await api.updatePromptTemplate(templateId, template);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update prompt template';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const deleteTemplate = useCallback(async (templateId: string) => {
    try {
      await api.deletePromptTemplate(templateId);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete prompt template';
      setError(message);
      throw err;
    }
  }, [loadData]);

  return {
    templates,
    loading,
    error,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    refreshData: loadData,
  };
}
