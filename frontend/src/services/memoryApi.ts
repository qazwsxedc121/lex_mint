import { api } from './apiClient';

import type {
  MemoryCreateRequest,
  MemoryItem,
  MemoryListResponse,
  MemorySearchRequest,
  MemorySearchResponse,
  MemorySettings,
  MemorySettingsUpdate,
  MemoryUpdateRequest,
} from '../types/memory';

/**
 * Get memory settings.
 */
export async function getMemorySettings(): Promise<MemorySettings> {
  const response = await api.get<MemorySettings>('/api/memory/settings');
  return response.data;
}

/**
 * Update memory settings.
 */
export async function updateMemorySettings(updates: MemorySettingsUpdate): Promise<void> {
  await api.put('/api/memory/settings', updates);
}

/**
 * List memory items.
 */
export async function listMemories(params?: {
  profile_id?: string;
  scope?: 'global' | 'assistant';
  assistant_id?: string;
  layer?: string;
  include_inactive?: boolean;
  limit?: number;
}): Promise<MemoryListResponse> {
  const response = await api.get<MemoryListResponse>('/api/memory', { params });
  return response.data;
}

/**
 * Create a memory item.
 */
export async function createMemory(payload: MemoryCreateRequest): Promise<MemoryItem> {
  const response = await api.post<{ message: string; item: MemoryItem }>('/api/memory', payload);
  return response.data.item;
}

/**
 * Update a memory item.
 */
export async function updateMemory(memoryId: string, payload: MemoryUpdateRequest): Promise<MemoryItem> {
  const response = await api.put<{ message: string; item: MemoryItem }>(`/api/memory/${memoryId}`, payload);
  return response.data.item;
}

/**
 * Delete a memory item.
 */
export async function deleteMemory(memoryId: string): Promise<void> {
  await api.delete(`/api/memory/${memoryId}`);
}

/**
 * Search memory items.
 */
export async function searchMemories(payload: MemorySearchRequest): Promise<MemorySearchResponse> {
  const response = await api.post<MemorySearchResponse>('/api/memory/search', payload);
  return response.data;
}
