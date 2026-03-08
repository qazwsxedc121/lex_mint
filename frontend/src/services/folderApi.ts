import { api } from './apiClient';

import type { Folder } from '../types/folder';

/**
 * List all chat folders.
 */
export async function listChatFolders(): Promise<Folder[]> {
  const response = await api.get<Folder[]>('/api/folders');
  return response.data;
}

/**
 * Create a new chat folder.
 */
export async function createChatFolder(name: string): Promise<Folder> {
  const response = await api.post<Folder>('/api/folders', { name });
  return response.data;
}

/**
 * Update chat folder name.
 */
export async function updateChatFolder(folderId: string, name: string): Promise<Folder> {
  const response = await api.put<Folder>(`/api/folders/${folderId}`, { name });
  return response.data;
}

/**
 * Delete a chat folder.
 * Sessions in this folder will be moved to ungrouped.
 */
export async function deleteChatFolder(folderId: string): Promise<void> {
  await api.delete(`/api/folders/${folderId}`);
}

/**
 * Reorder a chat folder to a new position.
 */
export async function reorderChatFolder(folderId: string, newOrder: number): Promise<Folder> {
  const response = await api.patch<Folder>(`/api/folders/${folderId}/order`, { order: newOrder });
  return response.data;
}

/**
 * Update session's folder assignment.
 */
export async function updateSessionFolder(
  sessionId: string,
  folderId: string | null,
  contextType: string = 'chat',
  projectId?: string,
): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.put(`/api/sessions/${sessionId}/folder?${params.toString()}`, { folder_id: folderId });
}