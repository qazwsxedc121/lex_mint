/**
 * API client for backend communication using axios.
 */

import axios from 'axios';
import type { Session, SessionDetail, ChatRequest, ChatResponse } from '../types/message';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Create a new conversation session.
 */
export async function createSession(): Promise<string> {
  const response = await api.post<{ session_id: string }>('/api/sessions');
  return response.data.session_id;
}

/**
 * Get all conversation sessions.
 */
export async function listSessions(): Promise<Session[]> {
  const response = await api.get<{ sessions: Session[] }>('/api/sessions');
  return response.data.sessions;
}

/**
 * Get a specific session with full message history.
 */
export async function getSession(sessionId: string): Promise<SessionDetail> {
  const response = await api.get<SessionDetail>(`/api/sessions/${sessionId}`);
  return response.data;
}

/**
 * Delete a conversation session.
 */
export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete(`/api/sessions/${sessionId}`);
}

/**
 * Send a message and receive AI response.
 */
export async function sendMessage(
  sessionId: string,
  message: string
): Promise<string> {
  const response = await api.post<ChatResponse>('/api/chat', {
    session_id: sessionId,
    message,
  } as ChatRequest);
  return response.data.response;
}

/**
 * Send a message and receive streaming AI response.
 * @param onChunk - Callback for each token received
 * @param onDone - Callback when stream completes
 * @param onError - Callback for errors
 */
export async function sendMessageStream(
  sessionId: string,
  message: string,
  onChunk: (chunk: string) => void,
  onDone: () => void,
  onError: (error: string) => void
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: sessionId,
      message,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    throw new Error('Response body is not readable');
  }

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      // 解码数据
      const chunk = decoder.decode(value, { stream: true });

      // SSE 格式：每行 "data: {json}\n\n"
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6); // 移除 "data: " 前缀
          try {
            const data = JSON.parse(dataStr);

            if (data.error) {
              onError(data.error);
              return;
            }

            if (data.done) {
              onDone();
              return;
            }

            if (data.chunk) {
              onChunk(data.chunk);
            }
          } catch (e) {
            // 忽略解析错误（可能是不完整的 JSON）
            console.warn('Failed to parse SSE data:', dataStr);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Check API health.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await api.get('/api/health');
    return response.data.status === 'ok';
  } catch {
    return false;
  }
}

export default api;
