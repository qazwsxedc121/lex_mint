import { API_BASE } from './apiBase';
import { api } from './apiClient';

import type { MutableRefObject } from 'react';

/**
 * Generate follow-up questions for a session on demand.
 */
export async function generateFollowups(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<string[]> {
  const params = new URLSearchParams();
  params.append('session_id', sessionId);
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }
  const response = await api.post<{ questions: string[] }>(`/api/followup/generate?${params.toString()}`);
  return response.data.questions;
}

/**
 * Export a session as a clean Markdown file and trigger browser download.
 */
export async function exportSession(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await fetch(`${API_BASE}/api/sessions/${sessionId}/export?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Export failed: ${response.status}`);
  }

  const disposition = response.headers.get('Content-Disposition') || '';
  let filename = 'conversation.md';
  const filenameMatch = disposition.match(/filename\*=UTF-8''(.+)/);
  if (filenameMatch) {
    filename = decodeURIComponent(filenameMatch[1]);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export interface ChatGPTImportSessionSummary {
  session_id: string;
  title: string;
  message_count: number;
}

export interface ChatGPTImportResult {
  imported: number;
  skipped: number;
  sessions: ChatGPTImportSessionSummary[];
  errors: string[];
}

async function importConversationFile(url: string, file: File): Promise<ChatGPTImportResult> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    let message = `Import failed: ${response.status}`;
    try {
      const error = await response.json();
      if (error?.detail) {
        message = error.detail;
      }
    } catch {
      // Ignore JSON parse error.
    }
    throw new Error(message);
  }

  return response.json();
}

/**
 * Import ChatGPT conversations from conversations.json export.
 */
export async function importChatGPTConversations(file: File): Promise<ChatGPTImportResult> {
  return importConversationFile(`${API_BASE}/api/sessions/import/chatgpt`, file);
}

/**
 * Import Markdown conversation file.
 */
export async function importMarkdownConversation(file: File): Promise<ChatGPTImportResult> {
  return importConversationFile(`${API_BASE}/api/sessions/import/markdown`, file);
}

/**
 * Synthesize text to speech via Edge TTS backend.
 * Returns audio as a Blob.
 */
export async function synthesizeSpeech(
  text: string,
  voice?: string,
  abortControllerRef?: MutableRefObject<AbortController | null>,
): Promise<Blob> {
  const controller = new AbortController();
  if (abortControllerRef) {
    abortControllerRef.current = controller;
  }

  const response = await fetch(`${API_BASE}/api/tts/synthesize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice }),
    signal: controller.signal,
  });

  if (!response.ok) {
    throw new Error(`TTS failed: ${response.status}`);
  }
  return response.blob();
}