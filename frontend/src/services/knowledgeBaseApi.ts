import axios from 'axios';

import { API_BASE } from './apiBase';
import { api } from './apiClient';

import type {
  KnowledgeBase,
  KnowledgeBaseChunk,
  KnowledgeBaseCreate,
  KnowledgeBaseDocument,
  KnowledgeBaseUpdate,
  RagConfig,
} from '../types/knowledgeBase';

/**
 * List all knowledge bases.
 */
export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  const response = await api.get<KnowledgeBase[]>('/api/knowledge-bases');
  return response.data;
}

/**
 * Get a specific knowledge base.
 */
export async function getKnowledgeBase(kbId: string): Promise<KnowledgeBase> {
  const response = await api.get<KnowledgeBase>(`/api/knowledge-bases/${kbId}`);
  return response.data;
}

/**
 * Create a new knowledge base.
 */
export async function createKnowledgeBase(kb: KnowledgeBaseCreate): Promise<KnowledgeBase> {
  const response = await api.post<KnowledgeBase>('/api/knowledge-bases', kb);
  return response.data;
}

/**
 * Update a knowledge base.
 */
export async function updateKnowledgeBase(kbId: string, kb: KnowledgeBaseUpdate): Promise<KnowledgeBase> {
  const response = await api.put<KnowledgeBase>(`/api/knowledge-bases/${kbId}`, kb);
  return response.data;
}

/**
 * Delete a knowledge base.
 */
export async function deleteKnowledgeBase(kbId: string): Promise<void> {
  await api.delete(`/api/knowledge-bases/${kbId}`);
}

/**
 * List documents in a knowledge base.
 */
export async function listDocuments(kbId: string): Promise<KnowledgeBaseDocument[]> {
  const response = await api.get<KnowledgeBaseDocument[]>(`/api/knowledge-bases/${kbId}/documents`);
  return response.data;
}

/**
 * List chunks in a knowledge base for developer inspection.
 */
export async function listKnowledgeBaseChunks(
  kbId: string,
  options?: { docId?: string; limit?: number },
): Promise<KnowledgeBaseChunk[]> {
  const params = new URLSearchParams();
  if (options?.docId) {
    params.append('doc_id', options.docId);
  }
  if (options?.limit) {
    params.append('limit', options.limit.toString());
  }

  const suffix = params.toString();
  const response = await api.get<KnowledgeBaseChunk[]>(
    `/api/knowledge-bases/${kbId}/chunks${suffix ? `?${suffix}` : ''}`,
  );
  return response.data;
}

/**
 * Upload a document to a knowledge base.
 */
export async function uploadDocument(
  kbId: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<KnowledgeBaseDocument> {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await axios.post<KnowledgeBaseDocument>(
      `${API_BASE}/api/knowledge-bases/${kbId}/documents/upload`,
      formData,
      {
        onUploadProgress: (event) => {
          const total = event.total ?? file.size;
          if (!total || total <= 0) {
            return;
          }
          const percent = Math.min(100, Math.round((event.loaded / total) * 100));
          onProgress?.(percent);
        },
      },
    );

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const data = error.response?.data;
      if (data && typeof data === 'object' && 'detail' in data) {
        const detailValue = (data as { detail?: unknown }).detail;
        const detail = Array.isArray(detailValue)
          ? detailValue
              .map((item) => {
                if (item && typeof item === 'object' && 'msg' in (item as Record<string, unknown>)) {
                  return String((item as { msg?: unknown }).msg ?? '');
                }
                return String(item ?? '');
              })
              .filter(Boolean)
              .join('; ')
          : String(detailValue ?? '');
        if (detail) {
          throw new Error(detail);
        }
      }
    }
    throw error instanceof Error ? error : new Error('Upload failed');
  }
}

/**
 * Delete a document from a knowledge base.
 */
export async function deleteDocument(kbId: string, docId: string): Promise<void> {
  await api.delete(`/api/knowledge-bases/${kbId}/documents/${docId}`);
}

/**
 * Reprocess a document.
 */
export async function reprocessDocument(kbId: string, docId: string): Promise<void> {
  await api.post(`/api/knowledge-bases/${kbId}/documents/${docId}/reprocess`);
}

/**
 * Get RAG configuration.
 */
export async function getRagConfig(): Promise<RagConfig> {
  const response = await api.get<RagConfig>('/api/rag/config');
  return response.data;
}

/**
 * Update RAG configuration.
 */
export async function updateRagConfig(config: Partial<RagConfig>): Promise<void> {
  await api.put('/api/rag/config', config);
}