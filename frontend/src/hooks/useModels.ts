/**
 * 模型管理 Hook
 *
 * 封装模型配置管理逻辑
 */

import { useState, useCallback, useEffect } from 'react';
import type { Provider, Model, DefaultConfig } from '../types/model';
import * as api from '../services/api';

export function useModels() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [defaultConfig, setDefaultConfig] = useState<DefaultConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载所有数据
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

  // 初始加载
  useEffect(() => {
    loadData();
  }, [loadData]);

  // ==================== 提供商操作 ====================

  const createProvider = useCallback(async (provider: Provider) => {
    try {
      await api.createProvider(provider);
      await loadData(); // 重新加载数据
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

  // ==================== 模型操作 ====================

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

  // ==================== 默认配置 ====================

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
