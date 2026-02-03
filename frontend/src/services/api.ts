/**
 * API client for backend communication using axios.
 */

import axios from 'axios';
import type { Session, SessionDetail, ChatRequest, ChatResponse, TokenUsage, CostInfo, UploadedFile } from '../types/message';
import type { Provider, Model, DefaultConfig } from '../types/model';
import type { Assistant, AssistantCreate, AssistantUpdate } from '../types/assistant';
import type { Project, ProjectCreate, ProjectUpdate, FileNode, FileContent } from '../types/project';
import type { MutableRefObject } from 'react';

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
export async function createSession(
  modelId?: string,
  assistantId?: string,
  contextType: string = 'chat',
  projectId?: string
): Promise<string> {
  const body: { model_id?: string; assistant_id?: string } = {};
  if (assistantId) {
    body.assistant_id = assistantId;
  } else if (modelId) {
    body.model_id = modelId;
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
 * Send a message and receive AI response.
 */
export async function sendMessage(
  sessionId: string,
  message: string,
  contextType: string = 'chat',
  projectId?: string
): Promise<string> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.post<ChatResponse>(`/api/chat?${params.toString()}`, {
    session_id: sessionId,
    message,
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
 * @param contextType - Context type (default: 'chat')
 * @param projectId - Optional project ID
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
  attachments?: UploadedFile[],
  onUserMessageId?: (messageId: string) => void,
  onAssistantMessageId?: (messageId: string) => void,
  contextType: string = 'chat',
  projectId?: string
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

        // 解码数据
        const chunk = decoder.decode(value, { stream: true });

        // SSE 格式：每�?"data: {json}\n\n"
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

              // Handle usage/cost event
              if (data.type === 'usage' && data.usage && onUsage) {
                onUsage(data.usage, data.cost);
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

              if (data.chunk) {
                onChunk(data.chunk);
              }
            } catch (e) {
              // 忽略解析错误（可能是不完整的 JSON�?              console.warn('Failed to parse SSE data:', dataStr);
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

// ==================== 文件附件 API ====================

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

// ==================== 模型管理 API ====================

/**
 * 获取所有提供商列表
 */
export async function listProviders(): Promise<Provider[]> {
  const response = await api.get<Provider[]>('/api/models/providers');
  return response.data;
}

/**
 * 获取指定提供�? */
export async function getProvider(providerId: string, includeMaskedKey: boolean = false): Promise<Provider> {
  const url = includeMaskedKey
    ? `/api/models/providers/${providerId}?include_masked_key=true`
    : `/api/models/providers/${providerId}`;
  const response = await api.get<Provider>(url);
  return response.data;
}

/**
 * 创建提供�? */
export async function createProvider(provider: Provider): Promise<void> {
  await api.post('/api/models/providers', provider);
}

/**
 * 更新提供�? */
export async function updateProvider(providerId: string, provider: Provider): Promise<void> {
  await api.put(`/api/models/providers/${providerId}`, provider);
}

/**
 * 删除提供商（级联删除关联模型�? */
export async function deleteProvider(providerId: string): Promise<void> {
  await api.delete(`/api/models/providers/${providerId}`);
}

/**
 * 获取模型列表
 * @param providerId - 可选的提供商ID，用于筛�? */
export async function listModels(providerId?: string): Promise<Model[]> {
  const url = providerId
    ? `/api/models/list?provider_id=${providerId}`
    : '/api/models/list';
  const response = await api.get<Model[]>(url);
  return response.data;
}

/**
 * 获取指定模型
 */
export async function getModel(modelId: string): Promise<Model> {
  const response = await api.get<Model>(`/api/models/list/${modelId}`);
  return response.data;
}

/**
 * 创建模型
 */
export async function createModel(model: Model): Promise<void> {
  await api.post('/api/models/list', model);
}

/**
 * 更新模型
 */
export async function updateModel(modelId: string, model: Model): Promise<void> {
  await api.put(`/api/models/list/${modelId}`, model);
}

/**
 * 删除模型
 */
export async function deleteModel(modelId: string): Promise<void> {
  await api.delete(`/api/models/list/${modelId}`);
}

/**
 * 测试模型连接
 */
export async function testModelConnection(modelId: string): Promise<{ success: boolean; message: string }> {
  const response = await api.post<{ success: boolean; message: string }>('/api/models/test-connection', {
    model_id: modelId
  });
  return response.data;
}

/**
 * 获取默认模型配置
 */
export async function getDefaultConfig(): Promise<DefaultConfig> {
  const response = await api.get<DefaultConfig>('/api/models/default');
  return response.data;
}

/**
 * 设置默认模型
 */
export async function setDefaultConfig(providerId: string, modelId: string): Promise<void> {
  await api.put(`/api/models/default?provider_id=${providerId}&model_id=${modelId}`);
}

/**
 * 获取支持 reasoning effort 的模型模式列�? */
export async function getReasoningSupportedPatterns(): Promise<string[]> {
  const response = await api.get<string[]>('/api/models/reasoning-patterns');
  return response.data;
}

/**
 * 更新会话使用的模�? */
export async function updateSessionModel(sessionId: string, modelId: string, contextType: string = 'chat', projectId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.put(`/api/sessions/${sessionId}/model?${params.toString()}`, { model_id: modelId });
}

/**
 * 更新会话使用的助�? */
export async function updateSessionAssistant(sessionId: string, assistantId: string, contextType: string = 'chat', projectId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.put(`/api/sessions/${sessionId}/assistant?${params.toString()}`, { assistant_id: assistantId });
}

// ==================== 助手管理 API ====================

/**
 * 获取所有助手列�? */
export async function listAssistants(): Promise<Assistant[]> {
  const response = await api.get<Assistant[]>('/api/assistants');
  return response.data;
}

/**
 * 获取指定助手
 */
export async function getAssistant(assistantId: string): Promise<Assistant> {
  const response = await api.get<Assistant>(`/api/assistants/${assistantId}`);
  return response.data;
}

/**
 * 创建助手
 */
export async function createAssistant(assistant: AssistantCreate): Promise<void> {
  await api.post('/api/assistants', assistant);
}

/**
 * 更新助手
 */
export async function updateAssistant(assistantId: string, assistant: AssistantUpdate): Promise<void> {
  await api.put(`/api/assistants/${assistantId}`, assistant);
}

/**
 * 删除助手（不能删除默认助手）
 */
export async function deleteAssistant(assistantId: string): Promise<void> {
  await api.delete(`/api/assistants/${assistantId}`);
}

/**
 * 获取默认助手ID
 */
export async function getDefaultAssistantId(): Promise<string> {
  const response = await api.get<{ default_assistant_id: string }>('/api/assistants/default/id');
  return response.data.default_assistant_id;
}

/**
 * 获取默认助手
 */
export async function getDefaultAssistant(): Promise<Assistant> {
  const response = await api.get<Assistant>('/api/assistants/default/assistant');
  return response.data;
}

/**
 * 设置默认助手
 */
export async function setDefaultAssistant(assistantId: string): Promise<void> {
  await api.put(`/api/assistants/default/${assistantId}`);
}

// ==================== 测试连接 ====================

/**
 * 测试提供商连接（使用提供的API Key�? */
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
 * 测试提供商连接（使用已存储的API Key�? */
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

// ==================== Provider 抽象�?API ====================

import type {
  BuiltinProviderInfo,
  ModelInfo,
  CapabilitiesResponse,
  ProtocolInfo,
} from '../types/model';

/**
 * 获取所有内�?Provider 定义
 */
export async function listBuiltinProviders(): Promise<BuiltinProviderInfo[]> {
  const response = await api.get<BuiltinProviderInfo[]>('/api/models/providers/builtin');
  return response.data;
}

/**
 * 获取指定内置 Provider 定义
 */
export async function getBuiltinProvider(providerId: string): Promise<BuiltinProviderInfo> {
  const response = await api.get<BuiltinProviderInfo>(`/api/models/providers/builtin/${providerId}`);
  return response.data;
}

/**
 * �?Provider API 获取可用模型列表
 */
export async function fetchProviderModels(providerId: string): Promise<ModelInfo[]> {
  const response = await api.post<ModelInfo[]>(`/api/models/providers/${providerId}/fetch-models`);
  return response.data;
}

/**
 * 获取模型的能力配置（合并 provider 默认 + model 覆盖�? */
export async function getModelCapabilities(modelId: string): Promise<CapabilitiesResponse> {
  const response = await api.get<CapabilitiesResponse>(`/api/models/capabilities/${modelId}`);
  return response.data;
}

/**
 * 获取可用�?API 协议类型
 */
export async function listProtocols(): Promise<ProtocolInfo[]> {
  const response = await api.get<ProtocolInfo[]>('/api/models/protocols');
  return response.data;
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

export default api;

