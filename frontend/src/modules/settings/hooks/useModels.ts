/**
 * Model management Hook
 *
 * Manages model configuration state and operations
 */

import { useState, useCallback, useEffect } from 'react';
import type { Provider, Model, DefaultConfig } from '../../../types/model';
import * as api from '../../../services/api';

export function useModels() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [defaultConfig, setDefaultConfig] = useState<DefaultConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load all data
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [providersData, modelsData, defaultData] = await Promise.all([
        api.listProviders(),
        api.listModels(),
        api.getDefaultConfig(),
      ]);
      setProviders(providersData);
      setModels(modelsData);
      setDefaultConfig(defaultData);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load model configuration';
      setError(message);
      console.error('Failed to load model configuration:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // ==================== Provider Operations ====================

  const createProvider = useCallback(async (provider: Provider) => {
    try {
      await api.createProvider(provider);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create provider';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const updateProvider = useCallback(async (providerId: string, provider: Provider) => {
    try {
      await api.updateProvider(providerId, provider);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update provider';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const deleteProvider = useCallback(async (providerId: string) => {
    try {
      await api.deleteProvider(providerId);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete provider';
      setError(message);
      throw err;
    }
  }, [loadData]);

  // ==================== Model Operations ====================

  const createModel = useCallback(async (model: Model) => {
    try {
      await api.createModel(model);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create model';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const updateModel = useCallback(async (modelId: string, model: Model) => {
    try {
      await api.updateModel(modelId, model);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update model';
      setError(message);
      throw err;
    }
  }, [loadData]);

  const deleteModel = useCallback(async (modelId: string) => {
    try {
      await api.deleteModel(modelId);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete model';
      setError(message);
      throw err;
    }
  }, [loadData]);

  // ==================== Default Config ====================

  const setDefault = useCallback(async (providerId: string, modelId: string) => {
    try {
      await api.setDefaultConfig(providerId, modelId);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to set default model';
      setError(message);
      throw err;
    }
  }, [loadData]);

  return {
    // State
    providers,
    models,
    defaultConfig,
    loading,
    error,

    // Operations
    createProvider,
    updateProvider,
    deleteProvider,
    createModel,
    updateModel,
    deleteModel,
    setDefault,
    refreshData: loadData,
  };
}
