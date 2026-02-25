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

const parseAliases = (value: unknown): string[] => {
  const rawItems = Array.isArray(value)
    ? value
    : typeof value === 'string'
      ? value.split(/[\n,]/)
      : [];

  const normalized: string[] = [];
  const seen = new Set<string>();
  for (const item of rawItems) {
    const alias = String(item).trim();
    if (!alias) {
      continue;
    }
    const lowered = alias.toLowerCase();
    if (seen.has(lowered)) {
      continue;
    }
    seen.add(lowered);
    normalized.push(alias);
  }
  return normalized;
};

const normalizePromptTemplatePayload = <T extends PromptTemplateCreate | PromptTemplateUpdate>(payload: T): T => {
  const nextPayload: Record<string, unknown> = { ...payload };
  for (const key of Object.keys(nextPayload)) {
    if (key.startsWith('__')) {
      delete nextPayload[key];
    }
  }

  if (typeof nextPayload.trigger === 'string') {
    nextPayload.trigger = nextPayload.trigger.trim();
  }
  if (Object.prototype.hasOwnProperty.call(nextPayload, 'aliases')) {
    nextPayload.aliases = parseAliases(nextPayload.aliases);
  }

  return nextPayload as T;
};

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
      await api.createPromptTemplate(normalizePromptTemplatePayload(template));
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create prompt template';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const updateTemplate = useCallback(async (templateId: string, template: PromptTemplateUpdate) => {
    try {
      await api.updatePromptTemplate(templateId, normalizePromptTemplatePayload(template));
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
