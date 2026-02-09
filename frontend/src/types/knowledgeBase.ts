/**
 * Knowledge Base type definitions
 */

export interface KnowledgeBase {
  id: string;
  name: string;
  description?: string;
  embedding_model?: string;
  chunk_size?: number;
  chunk_overlap?: number;
  document_count: number;
  enabled: boolean;
  created_at: string;
}

export interface KnowledgeBaseDocument {
  id: string;
  kb_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: 'pending' | 'processing' | 'ready' | 'error';
  chunk_count: number;
  error_message?: string;
  created_at: string;
}

export interface KnowledgeBaseChunk {
  id: string;
  kb_id: string;
  doc_id?: string;
  filename?: string;
  chunk_index: number;
  content: string;
}

export interface KnowledgeBaseCreate {
  id: string;
  name: string;
  description?: string;
  embedding_model?: string;
  chunk_size?: number;
  chunk_overlap?: number;
  enabled?: boolean;
}

export interface KnowledgeBaseUpdate {
  name?: string;
  description?: string;
  embedding_model?: string;
  chunk_size?: number;
  chunk_overlap?: number;
  enabled?: boolean;
}

export interface RagConfig {
  embedding_provider: string;
  embedding_api_model: string;
  embedding_api_base_url: string;
  embedding_api_key: string;
  embedding_local_model: string;
  embedding_local_device: string;
  chunk_size: number;
  chunk_overlap: number;
  top_k: number;
  score_threshold: number;
  persist_directory: string;
}
