/**
 * API client for backend communication using axios.
 */

import axios from 'axios';
import type { Session, SessionDetail, ChatRequest, ChatResponse, TokenUsage, CostInfo, UploadedFile, SearchSource, ParamOverrides, ContextInfo } from '../types/message';
import type { Provider, Model, DefaultConfig } from '../types/model';
import type { Assistant, AssistantCreate, AssistantUpdate } from '../types/assistant';
import type { Project, ProjectCreate, ProjectUpdate, FileNode, FileContent, FileRenameResult } from '../types/project';
import type { KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseDocument, KnowledgeBaseChunk, RagConfig } from '../types/knowledgeBase';
import type { MutableRefObject } from 'react';

const API_BASE = import.meta.env.VITE_API_URL;
if (!API_BASE) {
  throw new Error('VITE_API_URL is not configured. Set API_PORT in the root .env file.');
}

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Create a new conversation session.
 */
export async function createSession(
  modelId?: string,
  assistantId?: string,
  contextType: string = 'chat',
  projectId?: string,
  temporary: boolean = false
): Promise<string> {
  const body: { model_id?: string; assistant_id?: string; temporary?: boolean } = {};
  if (assistantId) {
    body.assistant_id = assistantId;
  } else if (modelId) {
    body.model_id = modelId;
  }
  if (temporary) {
    body.temporary = true;
  }

  // Build query params
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.post<{ session_id: string }>(
    `/api/sessions?${params.toString()}`,
    Object.keys(body).length > 0 ? body : undefined
  );
  return response.data.session_id;
}

/**
 * Get all conversation sessions.
 */
export async function listSessions(contextType: string = 'chat', projectId?: string): Promise<Session[]> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.get<{ sessions: Session[] }>(`/api/sessions?${params.toString()}`);
  return response.data.sessions;
}

/**
 * Get a specific session with full message history.
 */
export async function getSession(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<SessionDetail> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.get<SessionDetail>(`/api/sessions/${sessionId}?${params.toString()}`);
  return response.data;
}

/**
 * Delete a conversation session.
 */
export async function deleteSession(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.delete(`/api/sessions/${sessionId}?${params.toString()}`);
}

/**
 * Search result from backend session search.
 */
export interface SearchResult {
  session_id: string;
  title: string;
  created_at: string;
  message_count: number;
  match_type: 'title' | 'content';
  match_context: string;
}

/**
 * Search sessions by title and message content.
 */
export async function searchSessions(query: string, contextType: string = 'chat', projectId?: string): Promise<SearchResult[]> {
  const params = new URLSearchParams();
  params.append('q', query);
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.get<{ results: SearchResult[] }>(`/api/sessions/search?${params.toString()}`);
  return response.data.results;
}

/**
 * Save a temporary session (convert to permanent).
 */
export async function saveTemporarySession(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.post(`/api/sessions/${sessionId}/save?${params.toString()}`);
}

/**
 * Update session title
 */
export async function updateSessionTitle(sessionId: string, title: string, contextType: string = 'chat', projectId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.put(`/api/sessions/${sessionId}/title?${params.toString()}`, { title });
}

/**
 * Duplicate a session
 */
export async function duplicateSession(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<string> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.post<{ session_id: string; message: string }>(
    `/api/sessions/${sessionId}/duplicate?${params.toString()}`
  );
  return response.data.session_id;
}

/**
 * Branch a session from a specific message
 */
export async function branchSession(sessionId: string, messageId: string, contextType: string = 'chat', projectId?: string): Promise<string> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.post<{ session_id: string; message: string }>(
    `/api/sessions/${sessionId}/branch?${params.toString()}`,
    { message_id: messageId }
  );
  return response.data.session_id;
}

/**
 * Delete a single message from a conversation.
 */
export async function deleteMessage(sessionId: string, messageId: string, contextType: string = 'chat', projectId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.delete(`/api/chat/message?${params.toString()}`, {
    data: {
      session_id: sessionId,
      message_id: messageId,
      context_type: contextType,
      project_id: projectId,
    },
  });
}

/**
 * Update the content of a specific message (save only, no regeneration).
 */
export async function updateMessageContent(
  sessionId: string,
  messageId: string,
  content: string,
  contextType: string = 'chat',
  projectId?: string
): Promise<void> {
  await api.put('/api/chat/message', {
    session_id: sessionId,
    message_id: messageId,
    content,
    context_type: contextType,
    project_id: projectId,
  });
}

/**
 * Insert a separator into conversation to clear context
 */
export async function insertSeparator(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<string> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.post<{ success: boolean; message_id: string }>(
    `/api/chat/separator?${params.toString()}`,
    {
      session_id: sessionId,
      context_type: contextType,
      project_id: projectId,
    }
  );
  return response.data.message_id;
}

/**
 * Clear all messages from conversation
 */
export async function clearAllMessages(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.post(`/api/chat/clear?${params.toString()}`, {
    session_id: sessionId,
    context_type: contextType,
    project_id: projectId,
  });
}

/**
 * Compress conversation context by summarizing messages via LLM.
 * Streams the summary as SSE events.
 */
export async function compressContext(
  sessionId: string,
  onChunk: (chunk: string) => void,
  onComplete: (data: { message_id: string; compressed_count: number }) => void,
  onError: (error: string) => void,
  contextType: string = 'chat',
  projectId?: string,
  abortControllerRef?: MutableRefObject<AbortController | null>
): Promise<void> {
  const controller = new AbortController();
  if (abortControllerRef) {
    abortControllerRef.current = controller;
  }

  try {
    const response = await fetch(`${API_BASE}/api/chat/compress`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        context_type: contextType,
        project_id: projectId,
      }),
      signal: controller.signal,
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

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);

              if (data.error) {
                onError(data.error);
                return;
              }

              if (data.done) {
                return;
              }

              if (data.type === 'compression_complete') {
                onComplete({
                  message_id: data.message_id,
                  compressed_count: data.compressed_count,
                });
                continue;
              }

              if (data.chunk) {
                onChunk(data.chunk);
              }
            } catch (e) {
              // Ignore parse errors for partial chunks
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') {
      console.log('Compression aborted by user');
      return;
    }
    throw error;
  } finally {
    if (abortControllerRef) {
      abortControllerRef.current = null;
    }
  }
}

/**
 * Translate text via LLM streaming.
 * Streams the translation as SSE events.
 */
export async function translateText(
  text: string,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
  onError: (error: string) => void,
  targetLanguage?: string,
  modelId?: string,
  abortControllerRef?: MutableRefObject<AbortController | null>,
  useInputTargetLanguage?: boolean
): Promise<void> {
  const controller = new AbortController();
  if (abortControllerRef) {
    abortControllerRef.current = controller;
  }

  try {
    const body: any = { text };
    if (targetLanguage) body.target_language = targetLanguage;
    if (modelId) body.model_id = modelId;
    if (useInputTargetLanguage) body.use_input_target_language = true;

    const response = await fetch(`${API_BASE}/api/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
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

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);

              if (data.error) {
                onError(data.error);
                return;
              }

              if (data.done) {
                onComplete();
                return;
              }

              if (data.type === 'translation_complete') {
                continue;
              }

              if (data.chunk) {
                onChunk(data.chunk);
              }
            } catch (e) {
              // Ignore parse errors for partial chunks
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') {
      console.log('Translation aborted by user');
      return;
    }
    throw error;
  } finally {
    if (abortControllerRef) {
      abortControllerRef.current = null;
    }
  }
}

/**
 * Send a message and receive AI response.
 */
export async function sendMessage(
  sessionId: string,
  message: string,
  contextType: string = 'chat',
  projectId?: string,
  useWebSearch?: boolean
): Promise<string> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.post<ChatResponse>(`/api/chat?${params.toString()}`, {
    session_id: sessionId,
    message,
    use_web_search: useWebSearch || false,
  } as ChatRequest);
  return response.data.response;
}

/**
 * Send a message and receive streaming AI response.
 * @param sessionId - Session ID
 * @param message - User message
 * @param truncateAfterIndex - Optional index to truncate messages after
 * @param skipUserMessage - Whether to skip appending user message (for regeneration)
 * @param onChunk - Callback for each token received
 * @param onDone - Callback when stream completes
 * @param onError - Callback for errors
 * @param abortControllerRef - Optional ref to store AbortController for cancellation
 * @param reasoningEffort - Optional reasoning effort level: "low", "medium", "high"
 * @param onUsage - Optional callback for usage/cost data
 * @param attachments - Optional file attachments
 * @param onUserMessageId - Optional callback for user message ID from backend
 * @param onAssistantMessageId - Optional callback for assistant message ID from backend
 * @param onFollowupQuestions - Optional callback for follow-up question suggestions
 * @param contextType - Context type (default: 'chat')
 * @param projectId - Optional project ID
 * @param onContextInfo - Optional callback for context window info
 */
export async function sendMessageStream(
  sessionId: string,
  message: string,
  truncateAfterIndex: number | null,
  skipUserMessage: boolean,
  onChunk: (chunk: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
  abortControllerRef?: MutableRefObject<AbortController | null>,
  reasoningEffort?: string,
  onUsage?: (usage: TokenUsage, cost?: CostInfo) => void,
  onSources?: (sources: SearchSource[]) => void,
  attachments?: UploadedFile[],
  onUserMessageId?: (messageId: string) => void,
  onAssistantMessageId?: (messageId: string) => void,
  useWebSearch?: boolean,
  contextType: string = 'chat',
  projectId?: string,
  onFollowupQuestions?: (questions: string[]) => void,
  onContextInfo?: (info: ContextInfo) => void,
  onThinkingDuration?: (durationMs: number) => void
): Promise<void> {
  // Create AbortController for cancellation support
  const controller = new AbortController();
  if (abortControllerRef) {
    abortControllerRef.current = controller;
  }

  try {
    const requestBody: any = {
      session_id: sessionId,
      message,
      truncate_after_index: truncateAfterIndex,
      skip_user_message: skipUserMessage,
      reasoning_effort: reasoningEffort || null,
      context_type: contextType,
    };

    if (projectId) {
      requestBody.project_id = projectId;
    }

    if (useWebSearch) {
      requestBody.use_web_search = true;
    }

    if (attachments && attachments.length > 0) {
      requestBody.attachments = attachments.map(a => ({
        filename: a.filename,
        size: a.size,
        mime_type: a.mime_type,
        temp_path: a.temp_path,
      }));
    }

    const response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
      signal: controller.signal,
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

        const chunk = decoder.decode(value, { stream: true });

        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6); //  "data: " 
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

              // Handle usage/cost event
              if (data.type === 'usage' && data.usage && onUsage) {
                onUsage(data.usage, data.cost);
                continue;
              }

              // Handle sources event
              if (data.type === 'sources' && data.sources && onSources) {
                onSources(data.sources);
                continue;
              }

              // Handle user_message_id event
              if (data.type === 'user_message_id' && data.message_id && onUserMessageId) {
                onUserMessageId(data.message_id);
                continue;
              }

              // Handle assistant_message_id event
              if (data.type === 'assistant_message_id' && data.message_id && onAssistantMessageId) {
                onAssistantMessageId(data.message_id);
                continue;
              }

              // Handle followup_questions event
              if (data.type === 'followup_questions' && data.questions && onFollowupQuestions) {
                onFollowupQuestions(data.questions);
                continue;
              }

              // Handle context_info event
              if (data.type === 'context_info' && onContextInfo) {
                onContextInfo(data);
                continue;
              }

              // Handle thinking_duration event
              if (data.type === 'thinking_duration' && onThinkingDuration) {
                onThinkingDuration(data.duration_ms);
                continue;
              }

              if (data.chunk) {
                onChunk(data.chunk);
              }
            } catch (e) {
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  } catch (error: unknown) {
    // Handle abort as normal completion (keep partial content)
    if (error instanceof Error && error.name === 'AbortError') {
      console.log('Stream aborted by user');
      onDone();
      return;
    }
    throw error;
  } finally {
    // Clear the controller reference
    if (abortControllerRef) {
      abortControllerRef.current = null;
    }
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


/**
 * Upload a file attachment
 */
export async function uploadFile(
  sessionId: string,
  file: File,
  contextType: string = 'chat',
  projectId?: string
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
 * Download a file attachment
 */
export async function downloadFile(
  sessionId: string,
  messageIndex: number,
  filename: string
): Promise<Blob> {
  const response = await fetch(
    `${API_BASE}/api/chat/attachment/${sessionId}/${messageIndex}/${encodeURIComponent(filename)}`
  );

  if (!response.ok) {
    throw new Error('Download failed');
  }

  return response.blob();
}


/**
 * List providers.
 */
export async function listProviders(): Promise<Provider[]> {
  const response = await api.get<Provider[]>('/api/models/providers');
  return response.data;
}

/**
 * Get provider details.
 */
export async function getProvider(providerId: string, includeMaskedKey: boolean = false): Promise<Provider> {
  const url = includeMaskedKey
    ? `/api/models/providers/${providerId}?include_masked_key=true`
    : `/api/models/providers/${providerId}`;
  const response = await api.get<Provider>(url);
  return response.data;
}

/**
 * Create a provider.
 */
export async function createProvider(provider: Provider): Promise<void> {
  await api.post('/api/models/providers', provider);
}

/**
 * Update a provider.
 */
export async function updateProvider(providerId: string, provider: Provider): Promise<void> {
  await api.put(`/api/models/providers/${providerId}`, provider);
}

/**
 * Delete a provider (and related models).
 */
export async function deleteProvider(providerId: string): Promise<void> {
  await api.delete(`/api/models/providers/${providerId}`);
}

/**
 * List models.
 */
export async function listModels(providerId?: string): Promise<Model[]> {
  const url = providerId
    ? `/api/models/list?provider_id=${providerId}`
    : '/api/models/list';
  const response = await api.get<Model[]>(url);
  return response.data;
}

/**
 * Get a model.
 */
export async function getModel(modelId: string): Promise<Model> {
  const response = await api.get<Model>(`/api/models/list/${modelId}`);
  return response.data;
}

/**
 * Create a model.
 */
export async function createModel(model: Model): Promise<void> {
  await api.post('/api/models/list', model);
}

/**
 * Update a model.
 */
export async function updateModel(modelId: string, model: Model): Promise<void> {
  await api.put(`/api/models/list/${modelId}`, model);
}

/**
 * Delete a model.
 */
export async function deleteModel(modelId: string): Promise<void> {
  await api.delete(`/api/models/list/${modelId}`);
}

/**
 * Test model connection.
 */
export async function testModelConnection(modelId: string): Promise<{ success: boolean; message: string }> {
  const response = await api.post<{ success: boolean; message: string }>('/api/models/test-connection', {
    model_id: modelId
  });
  return response.data;
}

/**
 * Get default model configuration.
 */
export async function getDefaultConfig(): Promise<DefaultConfig> {
  const response = await api.get<DefaultConfig>('/api/models/default');
  return response.data;
}

/**
 * Set default model.
 */
export async function setDefaultConfig(providerId: string, modelId: string): Promise<void> {
  await api.put(`/api/models/default?provider_id=${providerId}&model_id=${modelId}`);
}

/**
 * Get reasoning supported patterns.
 */
export async function getReasoningSupportedPatterns(): Promise<string[]> {
  const response = await api.get<string[]>('/api/models/reasoning-patterns');
  return response.data;
}

/**
 * Update session model.
 */
export async function updateSessionModel(sessionId: string, modelId: string, contextType: string = 'chat', projectId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.put(`/api/sessions/${sessionId}/model?${params.toString()}`, { model_id: modelId });
}

/**
 * Update session assistant.
 */
export async function updateSessionAssistant(sessionId: string, assistantId: string, contextType: string = 'chat', projectId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.put(`/api/sessions/${sessionId}/assistant?${params.toString()}`, { assistant_id: assistantId });
}

/**
 * Update session parameter overrides.
 */
export async function updateSessionParamOverrides(
  sessionId: string,
  paramOverrides: ParamOverrides,
  contextType: string = 'chat',
  projectId?: string
): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.put(`/api/sessions/${sessionId}/param-overrides?${params.toString()}`, { param_overrides: paramOverrides });
}


/**
 * List Assistants.
 */
export async function listAssistants(): Promise<Assistant[]> {
  const response = await api.get<Assistant[]>('/api/assistants');
  return response.data;
}

/**
 * Get Assistant.
 */
export async function getAssistant(assistantId: string): Promise<Assistant> {
  const response = await api.get<Assistant>(`/api/assistants/${assistantId}`);
  return response.data;
}

/**
 * Create Assistant.
 */
export async function createAssistant(assistant: AssistantCreate): Promise<void> {
  await api.post('/api/assistants', assistant);
}

/**
 * Update Assistant.
 */
export async function updateAssistant(assistantId: string, assistant: AssistantUpdate): Promise<void> {
  await api.put(`/api/assistants/${assistantId}`, assistant);
}

/**
 * Delete Assistant.
 */
export async function deleteAssistant(assistantId: string): Promise<void> {
  await api.delete(`/api/assistants/${assistantId}`);
}

/**
 * Get Default Assistant Id.
 */
export async function getDefaultAssistantId(): Promise<string> {
  const response = await api.get<{ default_assistant_id: string }>('/api/assistants/default/id');
  return response.data.default_assistant_id;
}

/**
 * Get Default Assistant.
 */
export async function getDefaultAssistant(): Promise<Assistant> {
  const response = await api.get<Assistant>('/api/assistants/default/assistant');
  return response.data;
}

/**
 * Set Default Assistant.
 */
export async function setDefaultAssistant(assistantId: string): Promise<void> {
  await api.put(`/api/assistants/default/${assistantId}`);
}


/**
 * Test provider connection using a provided API key.
 */
export async function testProviderConnection(
  baseUrl: string,
  apiKey: string,
  modelId: string = 'gpt-3.5-turbo'
): Promise<{ success: boolean; message: string }> {
  const response = await api.post<{ success: boolean; message: string }>(
    '/api/models/providers/test',
    {
      base_url: baseUrl,
      api_key: apiKey,
      model_id: modelId,
    }
  );
  return response.data;
}

/**
 * Test provider connection using a stored API key.
 */
export async function testProviderStoredConnection(
  providerId: string,
  baseUrl: string,
  modelId: string = 'gpt-3.5-turbo'
): Promise<{ success: boolean; message: string }> {
  const response = await api.post<{ success: boolean; message: string }>(
    '/api/models/providers/test-stored',
    {
      provider_id: providerId,
      base_url: baseUrl,
      model_id: modelId,
    }
  );
  return response.data;
}


import type {
  BuiltinProviderInfo,
  ModelInfo,
  CapabilitiesResponse,
  ProtocolInfo,
} from '../types/model';

/**
 * List built-in providers.
 */
export async function listBuiltinProviders(): Promise<BuiltinProviderInfo[]> {
  const response = await api.get<BuiltinProviderInfo[]>('/api/models/providers/builtin');
  return response.data;
}

/**
 * Get built-in provider definition.
 */
export async function getBuiltinProvider(providerId: string): Promise<BuiltinProviderInfo> {
  const response = await api.get<BuiltinProviderInfo>(`/api/models/providers/builtin/${providerId}`);
  return response.data;
}

/**
 * Fetch available models from provider API.
 */
export async function fetchProviderModels(providerId: string): Promise<ModelInfo[]> {
  const response = await api.post<ModelInfo[]>(`/api/models/providers/${providerId}/fetch-models`);
  return response.data;
}

/**
 * Get model capabilities (provider defaults plus overrides).
 */
export async function getModelCapabilities(modelId: string): Promise<CapabilitiesResponse> {
  const response = await api.get<CapabilitiesResponse>(`/api/models/capabilities/${modelId}`);
  return response.data;
}

/**
 * List supported API protocol types.
 */
export async function listProtocols(): Promise<ProtocolInfo[]> {
  const response = await api.get<ProtocolInfo[]>('/api/models/protocols');
  return response.data;
}

// ==================== Search Config API ====================

export interface SearchConfig {
  provider: string;
  max_results: number;
  timeout_seconds: number;
}

export interface SearchConfigUpdate {
  provider?: string;
  max_results?: number;
  timeout_seconds?: number;
}

/**
 * Get search configuration
 */
export async function getSearchConfig(): Promise<SearchConfig> {
  const response = await api.get<SearchConfig>('/api/search/config');
  return response.data;
}

/**
 * Update search configuration
 */
export async function updateSearchConfig(updates: SearchConfigUpdate): Promise<void> {
  await api.put('/api/search/config', updates);
}

// ==================== Webpage Config API ====================

export interface WebpageConfig {
  enabled: boolean;
  max_urls: number;
  timeout_seconds: number;
  max_bytes: number;
  max_content_chars: number;
  user_agent: string;
  proxy?: string | null;
  trust_env: boolean;
  diagnostics_enabled: boolean;
  diagnostics_timeout_seconds: number;
}

export interface WebpageConfigUpdate {
  enabled?: boolean;
  max_urls?: number;
  timeout_seconds?: number;
  max_bytes?: number;
  max_content_chars?: number;
  user_agent?: string;
  proxy?: string | null;
  trust_env?: boolean;
  diagnostics_enabled?: boolean;
  diagnostics_timeout_seconds?: number;
}

/**
 * Get webpage configuration
 */
export async function getWebpageConfig(): Promise<WebpageConfig> {
  const response = await api.get<WebpageConfig>('/api/webpage/config');
  return response.data;
}

/**
 * Update webpage configuration
 */
export async function updateWebpageConfig(updates: WebpageConfigUpdate): Promise<void> {
  await api.put('/api/webpage/config', updates);
}

// ==================== Title Generation API ====================

export interface TitleGenerationConfig {
  enabled: boolean;
  trigger_threshold: number;
  model_id: string;
  prompt_template: string;
  max_context_rounds: number;
  timeout_seconds: number;
}

export interface TitleGenerationConfigUpdate {
  enabled?: boolean;
  trigger_threshold?: number;
  model_id?: string;
  prompt_template?: string;
  max_context_rounds?: number;
  timeout_seconds?: number;
}

/**
 * Get title generation configuration
 */
export async function getTitleGenerationConfig(): Promise<TitleGenerationConfig> {
  const response = await api.get<TitleGenerationConfig>('/api/title-generation/config');
  return response.data;
}

/**
 * Update title generation configuration
 */
export async function updateTitleGenerationConfig(updates: TitleGenerationConfigUpdate): Promise<void> {
  await api.put('/api/title-generation/config', updates);
}

/**
 * Manually trigger title generation for a session
 */
export async function generateTitleManually(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<{ message: string; title: string }> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.post<{ message: string; title: string }>(`/api/title-generation/generate?${params.toString()}`, {
    session_id: sessionId
  });
  return response.data;
}

// ==================== Project Management API ====================

/**
 * Get all projects
 */
export async function listProjects(): Promise<Project[]> {
  const response = await api.get<Project[]>('/api/projects');
  return response.data;
}

/**
 * Create a new project
 */
export async function createProject(project: ProjectCreate): Promise<Project> {
  const response = await api.post<Project>('/api/projects', project);
  return response.data;
}

/**
 * Get a specific project
 */
export async function getProject(id: string): Promise<Project> {
  const response = await api.get<Project>(`/api/projects/${id}`);
  return response.data;
}

/**
 * Update a project
 */
export async function updateProject(id: string, data: ProjectUpdate): Promise<Project> {
  const response = await api.put<Project>(`/api/projects/${id}`, data);
  return response.data;
}

/**
 * Delete a project
 */
export async function deleteProject(id: string): Promise<void> {
  await api.delete(`/api/projects/${id}`);
}

/**
 * Get file tree for a project
 */
export async function getFileTree(id: string, path?: string): Promise<FileNode> {
  const url = path ? `/api/projects/${id}/tree?path=${encodeURIComponent(path)}` : `/api/projects/${id}/tree`;
  const response = await api.get<FileNode>(url);
  return response.data;
}

/**
 * Create a new file in a project
 */
export async function createFile(
  id: string,
  path: string,
  content: string = '',
  encoding: string = 'utf-8'
): Promise<FileContent> {
  const response = await api.post<FileContent>(`/api/projects/${id}/files`, {
    path,
    content,
    encoding
  });
  return response.data;
}

/**
 * Create a new folder in a project
 */
export async function createFolder(id: string, path: string): Promise<FileNode> {
  const response = await api.post<FileNode>(`/api/projects/${id}/directories`, {
    path
  });
  return response.data;
}

/**
 * Delete a folder from a project
 */
export async function deleteFolder(id: string, path: string, recursive: boolean = false): Promise<void> {
  await api.delete(`/api/projects/${id}/directories`, {
    params: {
      path,
      recursive
    }
  });
}

/**
 * Delete a file from a project
 */
export async function deleteFile(id: string, path: string): Promise<void> {
  await api.delete(`/api/projects/${id}/files`, {
    params: {
      path
    }
  });
}
/**
 * Read file content from a project
 */
export async function readFile(id: string, path: string): Promise<FileContent> {
  const response = await api.get<FileContent>(`/api/projects/${id}/files?path=${encodeURIComponent(path)}`);
  return response.data;
}

/**
 * Write content to a file in a project
 */
export async function writeFile(id: string, path: string, content: string, encoding: string = 'utf-8'): Promise<FileContent> {
  const response = await api.put<FileContent>(`/api/projects/${id}/files`, {
    path,
    content,
    encoding
  });
  return response.data;
}

/**
 * Rename or move a file or directory in a project
 */
export async function renameProjectPath(id: string, sourcePath: string, targetPath: string): Promise<FileRenameResult> {
  const response = await api.put<FileRenameResult>(`/api/projects/${id}/paths/rename`, {
    source_path: sourcePath,
    target_path: targetPath
  });
  return response.data;
}

/**
 * Generate follow-up questions for a session on demand
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

  const response = await fetch(
    `${API_BASE}/api/sessions/${sessionId}/export?${params.toString()}`
  );

  if (!response.ok) {
    throw new Error(`Export failed: ${response.status}`);
  }

  // Extract filename from Content-Disposition header
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

/**
 * Import ChatGPT conversations from conversations.json export.
 */
export async function importChatGPTConversations(file: File): Promise<ChatGPTImportResult> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/api/sessions/import/chatgpt`, {
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
      // Ignore JSON parse error
    }
    throw new Error(message);
  }

  return response.json();
}

/**
 * Import Markdown conversation file.
 */
export async function importMarkdownConversation(file: File): Promise<ChatGPTImportResult> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/api/sessions/import/markdown`, {
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
      // Ignore JSON parse error
    }
    throw new Error(message);
  }

  return response.json();
}

export default api;

/**
 * Synthesize text to speech via Edge TTS backend.
 * Returns audio as a Blob.
 */
export async function synthesizeSpeech(
  text: string,
  voice?: string,
  abortControllerRef?: MutableRefObject<AbortController | null>
): Promise<Blob> {
  const controller = new AbortController();
  if (abortControllerRef) abortControllerRef.current = controller;

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

// ==================== Knowledge Base API ====================

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
  options?: { docId?: string; limit?: number }
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
    `/api/knowledge-bases/${kbId}/chunks${suffix ? `?${suffix}` : ''}`
  );
  return response.data;
}

/**
 * Upload a document to a knowledge base.
 */
export async function uploadDocument(kbId: string, file: File): Promise<KnowledgeBaseDocument> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/api/knowledge-bases/${kbId}/documents/upload`, {
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

// ==================== RAG Config API ====================

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
