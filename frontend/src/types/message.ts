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
  title: string;
  url: string;
  snippet?: string;
  score?: number;
}

export interface UploadedFile {
  filename: string;
  size: number;
  mime_type: string;
  temp_path: string;
}

export interface Message {
  message_id?: string;  // UUID for each message (optional for backward compatibility)
  role: 'user' | 'assistant' | 'separator' | 'summary';
  content: string;
  attachments?: FileAttachment[];
  usage?: TokenUsage;
  cost?: CostInfo;
  sources?: SearchSource[];
}

export interface Session {
  session_id: string;
  title: string;
  created_at: string;
  message_count?: number;
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
