/**
 * Type definitions for messages and chat-related data structures.
 */

export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export interface Session {
  session_id: string;
  title: string;
  created_at: string;
  message_count?: number;
}

export interface SessionDetail {
  session_id: string;
  title: string;
  created_at: string;
  model_id: string;  // 新增：会话使用的模型 ID
  state: {
    messages: Message[];
    current_step: number;
  };
}

export interface ChatRequest {
  session_id: string;
  message: string;
}

export interface ChatResponse {
  session_id: string;
  response: string;
}
