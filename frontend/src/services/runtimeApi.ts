import { API_BASE } from './apiBase';

import type { UploadedFile } from '../types/message';

/**
 * Check API health.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/api/health`);
    if (!response.ok) {
      return false;
    }
    const data = await response.json() as { status?: string };
    return data.status === 'ok';
  } catch {
    return false;
  }
}

/**
 * Upload a file attachment.
 */
export async function uploadFile(
  sessionId: string,
  file: File,
  contextType: string = 'chat',
  projectId?: string,
): Promise<UploadedFile> {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  formData.append('file', file);

  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await fetch(`${API_BASE}/api/chat/upload?${params.toString()}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Upload failed');
  }

  return response.json();
}

/**
 * Download a file attachment.
 */
export async function downloadFile(
  sessionId: string,
  messageIndex: number,
  filename: string,
): Promise<Blob> {
  const response = await fetch(
    `${API_BASE}/api/chat/attachment/${sessionId}/${messageIndex}/${encodeURIComponent(filename)}`,
  );

  if (!response.ok) {
    throw new Error('Download failed');
  }

  return response.blob();
}
