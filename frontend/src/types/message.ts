/**
 * Type definitions for messages and chat-related data structures.
 */

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  reasoning_tokens?: number;
}

export interface CostInfo {
  input_cost: number;
  output_cost: number;
  total_cost: number;
  currency: string;
}

export interface ContextInfo {
  context_budget: number;
  context_window: number;
}

export interface FileAttachment {
  filename: string;
  size: number;
  mime_type: string;
}

export interface SearchSource {
  type?: 'search' | 'webpage' | 'rag' | 'memory' | 'rag_diagnostics';
  id?: string;
  title?: string;
  url?: string;
  snippet?: string;
  score?: number;
  content?: string;
  scope?: 'global' | 'assistant';
  layer?: 'identity' | 'preference' | 'context' | 'experience' | 'activity';
  kb_id?: string;
  doc_id?: string;
  filename?: string;
  chunk_index?: number;
  rerank_score?: number;
  final_score?: number;
  raw_count?: number;
  deduped_count?: number;
  diversified_count?: number;
  selected_count?: number;
  top_k?: number;
  recall_k?: number;
  vector_recall_k?: number;
  bm25_recall_k?: number;
  bm25_min_term_coverage?: number;
  fusion_top_k?: number;
  fusion_strategy?: 'rrf';
  retrieval_mode?: 'vector' | 'bm25' | 'hybrid';
  vector_weight?: number;
  bm25_weight?: number;
  rrf_k?: number;
  score_threshold?: number;
  max_per_doc?: number;
  reorder_strategy?: 'none' | 'long_context';
  searched_kb_count?: number;
  requested_kb_count?: number;
  best_score?: number;
  vector_raw_count?: number;
  bm25_raw_count?: number;
  query_transform_enabled?: boolean;
  query_transform_mode?: 'none' | 'rewrite';
  query_transform_applied?: boolean;
  query_transform_model_id?: string;
  query_transform_guard_blocked?: boolean;
  query_transform_guard_reason?: string;
  query_transform_crag_enabled?: boolean;
  query_transform_crag_quality_score?: number;
  query_transform_crag_quality_label?: 'correct' | 'ambiguous' | 'incorrect' | 'skipped';
  query_transform_crag_decision?: string;
  query_original?: string;
  query_effective?: string;
  rerank_enabled?: boolean;
  rerank_applied?: boolean;
  rerank_weight?: number;
  rerank_model?: string;
}

export interface UploadedFile {
  filename: string;
  size: number;
  mime_type: string;
  temp_path: string;
}

export interface CompareModelResponse {
  model_id: string;
  model_name: string;
  content: string;
  usage?: TokenUsage;
  cost?: CostInfo;
  thinking_content?: string;
  error?: string;
}

export interface Message {
  message_id?: string;  // UUID for each message (optional for backward compatibility)
  role: 'user' | 'assistant' | 'separator' | 'summary';
  content: string;
  created_at?: string;  // Timestamp from markdown header (YYYY-MM-DD HH:MM:SS)
  attachments?: FileAttachment[];
  usage?: TokenUsage;
  cost?: CostInfo;
  sources?: SearchSource[];
  thinkingDurationMs?: number;
  compareResponses?: CompareModelResponse[];
  assistant_id?: string;       // Group chat: which assistant generated this message
  assistant_name?: string;     // Group chat: assistant display name
  assistant_icon?: string;     // Group chat: Lucide icon key
}

export interface Session {
  session_id: string;
  title: string;
  created_at: string;
  updated_at?: string;  // File modification time (YYYY-MM-DD HH:MM:SS)
  message_count?: number;
  temporary?: boolean;
  folder_id?: string;  // Chat folder ID (optional)
  group_assistants?: string[];  // Group chat: list of assistant IDs
}

export interface ParamOverrides {
  model_id?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  top_k?: number;
  frequency_penalty?: number;
  presence_penalty?: number;
  max_rounds?: number;
}

export interface SessionDetail {
  session_id: string;
  title: string;
  created_at: string;
  model_id: string;  // Composite model ID
  assistant_id?: string;
  param_overrides?: ParamOverrides;
  total_usage?: TokenUsage;
  total_cost?: CostInfo;
  temporary?: boolean;
  compare_data?: Record<string, { responses: CompareModelResponse[] }>;
  group_assistants?: string[];  // Group chat: list of assistant IDs
  state: {
    messages: Message[];
    current_step: number;
  };
}

export interface ChatRequest {
  session_id: string;
  message: string;
  use_web_search?: boolean;
  search_query?: string;
}

export interface ChatResponse {
  session_id: string;
  response: string;
  sources?: SearchSource[];
}
