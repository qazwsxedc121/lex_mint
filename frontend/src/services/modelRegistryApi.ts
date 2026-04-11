import { api } from './apiClient';

import type { DefaultConfig, Model, Provider, ProviderPluginStatus } from '../types/model';

/**
 * List providers.
 */
export async function listProviders(enabledOnly: boolean = false): Promise<Provider[]> {
  const url = enabledOnly
    ? '/api/models/providers?enabled_only=true'
    : '/api/models/providers';
  const response = await api.get<Provider[]>(url);
  return response.data;
}

/**
 * Get provider details.
 */
export async function getProvider(providerId: string, includeMaskedKey: boolean = false): Promise<Provider> {
  const url = includeMaskedKey
    ? `/api/models/providers/${providerId}?include_masked_key=true`
    : `/api/models/providers/${providerId}`;
  const response = await api.get<Provider>(url);
  return response.data;
}

/**
 * Create a provider.
 */
export async function createProvider(provider: Provider): Promise<void> {
  await api.post('/api/models/providers', provider);
}

/**
 * Update a provider.
 */
export async function updateProvider(providerId: string, provider: Provider): Promise<void> {
  await api.put(`/api/models/providers/${providerId}`, provider);
}

/**
 * Delete a provider (and related models).
 */
export async function deleteProvider(providerId: string): Promise<void> {
  await api.delete(`/api/models/providers/${providerId}`);
}

/**
 * List models.
 */
export async function listModels(providerId?: string, enabledOnly: boolean = false): Promise<Model[]> {
  const params = new URLSearchParams();
  if (providerId) {
    params.append('provider_id', providerId);
  }
  if (enabledOnly) {
    params.append('enabled_only', 'true');
  }
  const suffix = params.toString();
  const url = suffix ? `/api/models/list?${suffix}` : '/api/models/list';
  const response = await api.get<Model[]>(url);
  return response.data;
}

/**
 * Get a model.
 */
export async function getModel(modelId: string): Promise<Model> {
  const response = await api.get<Model>(`/api/models/list/${modelId}`);
  return response.data;
}

/**
 * Create a model.
 */
export async function createModel(model: Model): Promise<void> {
  await api.post('/api/models/list', model);
}

/**
 * Update a model.
 */
export async function updateModel(modelId: string, model: Model): Promise<void> {
  await api.put(`/api/models/list/${modelId}`, model);
}

/**
 * Delete a model.
 */
export async function deleteModel(modelId: string): Promise<void> {
  await api.delete(`/api/models/list/${modelId}`);
}

/**
 * Test model connection.
 */
export async function testModelConnection(modelId: string): Promise<{ success: boolean; message: string }> {
  const response = await api.post<{ success: boolean; message: string }>('/api/models/test-connection', {
    model_id: modelId,
  });
  return response.data;
}

/**
 * Get default model configuration.
 */
export async function getDefaultConfig(): Promise<DefaultConfig> {
  const response = await api.get<DefaultConfig>('/api/models/default');
  return response.data;
}

/**
 * Set default model.
 */
export async function setDefaultConfig(providerId: string, modelId: string): Promise<void> {
  await api.put(`/api/models/default?provider_id=${providerId}&model_id=${modelId}`);
}

/**
 * Get reasoning supported patterns.
 */
export async function getReasoningSupportedPatterns(): Promise<string[]> {
  const response = await api.get<string[]>('/api/models/reasoning-patterns');
  return response.data;
}

/**
 * List provider plugin statuses.
 */
export async function listProviderPlugins(): Promise<ProviderPluginStatus[]> {
  const response = await api.get<ProviderPluginStatus[]>('/api/models/providers/plugins');
  return response.data;
}
