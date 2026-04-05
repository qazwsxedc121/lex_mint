import { api } from './apiClient';

import type { Assistant, AssistantCreate, AssistantUpdate } from '../types/assistant';
import type {
  BuiltinProviderInfo,
  CapabilitiesResponse,
  ModelInfo,
  ProtocolInfo,
  ProviderEndpointProbeRequest,
  ProviderEndpointProbeResponse,
  ProviderEndpointProfilesResponse,
} from '../types/model';

/**
 * List assistants.
 */
export async function listAssistants(enabledOnly: boolean = false): Promise<Assistant[]> {
  const url = enabledOnly ? '/api/assistants?enabled_only=true' : '/api/assistants';
  const response = await api.get<Assistant[]>(url);
  return response.data;
}

/**
 * Get assistant.
 */
export async function getAssistant(assistantId: string): Promise<Assistant> {
  const response = await api.get<Assistant>(`/api/assistants/${assistantId}`);
  return response.data;
}

/**
 * Create assistant.
 */
export async function createAssistant(assistant: AssistantCreate): Promise<void> {
  await api.post('/api/assistants', assistant);
}

/**
 * Update assistant.
 */
export async function updateAssistant(assistantId: string, assistant: AssistantUpdate): Promise<void> {
  await api.put(`/api/assistants/${assistantId}`, assistant);
}

/**
 * Delete assistant.
 */
export async function deleteAssistant(assistantId: string): Promise<void> {
  await api.delete(`/api/assistants/${assistantId}`);
}

/**
 * Get default assistant id.
 */
export async function getDefaultAssistantId(): Promise<string> {
  const response = await api.get<{ default_assistant_id: string }>('/api/assistants/default/id');
  return response.data.default_assistant_id;
}

/**
 * Get default assistant.
 */
export async function getDefaultAssistant(): Promise<Assistant> {
  const response = await api.get<Assistant>('/api/assistants/default/assistant');
  return response.data;
}

/**
 * Set default assistant.
 */
export async function setDefaultAssistant(assistantId: string): Promise<void> {
  await api.put(`/api/assistants/default/${assistantId}`);
}

/**
 * Test provider connection using a provided API key.
 */
export async function testProviderConnection(
  providerId: string,
  baseUrl: string,
  apiKey: string,
  modelId?: string,
): Promise<{ success: boolean; message: string }> {
  const response = await api.post<{ success: boolean; message: string }>(
    '/api/models/providers/test',
    {
      base_url: baseUrl,
      api_key: apiKey,
      provider_id: providerId,
      model_id: modelId,
    },
  );
  return response.data;
}

/**
 * Test provider connection using a stored API key.
 */
export async function testProviderStoredConnection(
  providerId: string,
  baseUrl: string,
  modelId?: string,
): Promise<{ success: boolean; message: string }> {
  const response = await api.post<{ success: boolean; message: string }>(
    '/api/models/providers/test-stored',
    {
      provider_id: providerId,
      base_url: baseUrl,
      model_id: modelId,
    },
  );
  return response.data;
}

/**
 * Probe provider endpoints (auto/manual diagnostics).
 */
export async function probeProviderEndpoints(
  providerId: string,
  payload: ProviderEndpointProbeRequest,
): Promise<ProviderEndpointProbeResponse> {
  const response = await api.post<ProviderEndpointProbeResponse>(
    `/api/models/providers/${providerId}/probe-endpoints`,
    payload,
  );
  return response.data;
}

/**
 * List endpoint profiles for a provider.
 */
export async function listProviderEndpointProfiles(
  providerId: string,
  clientRegionHint: 'cn' | 'global' | 'unknown' = 'unknown',
): Promise<ProviderEndpointProfilesResponse> {
  const response = await api.get<ProviderEndpointProfilesResponse>(
    `/api/models/providers/${providerId}/endpoint-profiles?client_region_hint=${clientRegionHint}`,
  );
  return response.data;
}

/**
 * List built-in providers.
 */
export async function listBuiltinProviders(): Promise<BuiltinProviderInfo[]> {
  const response = await api.get<BuiltinProviderInfo[]>('/api/models/providers/builtin');
  return response.data;
}

/**
 * Get built-in provider definition.
 */
export async function getBuiltinProvider(providerId: string): Promise<BuiltinProviderInfo> {
  const response = await api.get<BuiltinProviderInfo>(`/api/models/providers/builtin/${providerId}`);
  return response.data;
}

/**
 * Fetch available models from provider API.
 */
export async function fetchProviderModels(providerId: string): Promise<ModelInfo[]> {
  const response = await api.post<ModelInfo[]>(`/api/models/providers/${providerId}/fetch-models`);
  return response.data;
}

/**
 * Get model capabilities (provider defaults plus overrides).
 */
export async function getModelCapabilities(modelId: string): Promise<CapabilitiesResponse> {
  const response = await api.get<CapabilitiesResponse>(`/api/models/capabilities/${modelId}`);
  return response.data;
}

/**
 * List supported API protocol types.
 */
export async function listProtocols(): Promise<ProtocolInfo[]> {
  const response = await api.get<ProtocolInfo[]>('/api/models/protocols');
  return response.data;
}
