import { api } from './apiClient';

import type { ParamOverrides, Session, SessionDetail } from '../types/message';

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
 * Create a new conversation session.
 */
export async function createSession(
  modelId?: string,
  assistantId?: string,
  contextType: string = 'chat',
  projectId?: string,
  temporary: boolean = false,
  groupAssistants?: string[],
  groupMode?: 'round_robin' | 'committee',
  groupSettings?: Record<string, unknown>,
  targetType?: 'assistant' | 'model',
): Promise<string> {
  const body: {
    model_id?: string;
    assistant_id?: string;
    target_type?: 'assistant' | 'model';
    temporary?: boolean;
    group_assistants?: string[];
    group_mode?: 'round_robin' | 'committee';
    group_settings?: Record<string, unknown>;
  } = {};
  if (targetType) {
    body.target_type = targetType;
  }
  if (assistantId) {
    body.assistant_id = assistantId;
  } else if (modelId) {
    body.model_id = modelId;
  }
  if (temporary) {
    body.temporary = true;
  }
  if (groupAssistants && groupAssistants.length >= 2) {
    body.group_assistants = groupAssistants;
    body.group_mode = groupMode || 'round_robin';
    if (groupSettings && Object.keys(groupSettings).length > 0) {
      body.group_settings = groupSettings;
    }
  }

  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.post<{ session_id: string }>(
    `/api/sessions?${params.toString()}`,
    Object.keys(body).length > 0 ? body : undefined,
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
 * Get a specific session and its full contents.
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
 * Permanently save a temporary session.
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
 * Update session title.
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
 * Duplicate session into a new session id.
 */
export async function duplicateSession(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<string> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }
  const response = await api.post<{ session_id: string }>(`/api/sessions/${sessionId}/duplicate?${params.toString()}`);
  return response.data.session_id;
}

export async function moveSession(
  sessionId: string,
  targetContextType: string,
  targetProjectId?: string,
): Promise<void>;
export async function moveSession(
  sessionId: string,
  contextType: string,
  projectId: string | undefined,
  targetContextType: string,
  targetProjectId?: string,
): Promise<void>;
export async function moveSession(
  sessionId: string,
  arg2: string,
  arg3?: string,
  arg4?: string,
  arg5?: string,
): Promise<void> {
  const contextType = arg4 ? arg2 : 'chat';
  const projectId = arg4 ? arg3 : undefined;
  const targetContextType = arg4 || arg2;
  const targetProjectId = arg4 ? arg5 : arg3;

  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.post(
    `/api/sessions/${sessionId}/move?${params.toString()}`,
    {
      target_context_type: targetContextType,
      target_project_id: targetProjectId,
    },
  );
}

export async function copySession(
  sessionId: string,
  targetContextType: string,
  targetProjectId?: string,
): Promise<string>;
export async function copySession(
  sessionId: string,
  contextType: string,
  projectId: string | undefined,
  targetContextType: string,
  targetProjectId?: string,
): Promise<string>;
export async function copySession(
  sessionId: string,
  arg2: string,
  arg3?: string,
  arg4?: string,
  arg5?: string,
): Promise<string> {
  const contextType = arg4 ? arg2 : 'chat';
  const projectId = arg4 ? arg3 : undefined;
  const targetContextType = arg4 || arg2;
  const targetProjectId = arg4 ? arg5 : arg3;

  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.post<{ session_id: string }>(
    `/api/sessions/${sessionId}/copy?${params.toString()}`,
    {
      target_context_type: targetContextType,
      target_project_id: targetProjectId,
    },
  );
  return response.data.session_id;
}

/**
 * Branch session from a specific message.
 */
export async function branchSession(sessionId: string, messageId: string, contextType: string = 'chat', projectId?: string): Promise<string> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.post<{ session_id: string; message: string }>(
    `/api/sessions/${sessionId}/branch?${params.toString()}`,
    { message_id: messageId },
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
  await api.delete(`/api/sessions/${sessionId}/messages/${messageId}?${params.toString()}`);
}

/**
 * Update message content.
 */
export async function updateMessageContent(
  sessionId: string,
  messageId: string,
  content: string,
  contextType: string = 'chat',
  projectId?: string,
): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }
  await api.put(`/api/sessions/${sessionId}/messages/${messageId}?${params.toString()}`, { content });
}

/**
 * Insert separator.
 */
export async function insertSeparator(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<string> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }
  const response = await api.post<{ message_id: string }>(`/api/sessions/${sessionId}/separator?${params.toString()}`);
  return response.data.message_id;
}

/**
 * Clear all messages.
 */
export async function clearAllMessages(sessionId: string, contextType: string = 'chat', projectId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }
  await api.delete(`/api/sessions/${sessionId}/messages?${params.toString()}`);
}

/**
 * Update model for a session.
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
 * Update assistant for a session.
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
 * Update target for a session.
 */
export async function updateSessionTarget(
  sessionId: string,
  targetType: 'assistant' | 'model',
  options?: { assistantId?: string; modelId?: string },
): Promise<void>;
export async function updateSessionTarget(
  sessionId: string,
  targetType: 'assistant' | 'model',
  contextType: string,
  projectId?: string,
  options?: { assistantId?: string; modelId?: string },
): Promise<void>;
export async function updateSessionTarget(
  sessionId: string,
  targetType: 'assistant' | 'model',
  arg3?: string | { assistantId?: string; modelId?: string },
  arg4?: string,
  arg5?: { assistantId?: string; modelId?: string },
): Promise<void> {
  const usesLegacyOrder = typeof arg3 === 'string' || arg4 !== undefined || arg5 !== undefined;
  const contextType = usesLegacyOrder && typeof arg3 === 'string' ? arg3 : 'chat';
  const projectId = usesLegacyOrder ? arg4 : undefined;
  const options = usesLegacyOrder ? arg5 : arg3;

  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.put(`/api/sessions/${sessionId}/target?${params.toString()}`, {
    target_type: targetType,
    assistant_id: options?.assistantId,
    model_id: options?.modelId,
  });
}

/**
 * Update group assistant order for a session.
 */
export async function updateGroupAssistants(
  sessionId: string,
  groupAssistants: string[],
  contextType: string = 'chat',
  projectId?: string,
): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.put(`/api/sessions/${sessionId}/group-assistants?${params.toString()}`, {
    group_assistants: groupAssistants,
  });
}

/**
 * Update session parameter overrides.
 */
export async function updateSessionParamOverrides(
  sessionId: string,
  paramOverrides: ParamOverrides,
  contextType: string = 'chat',
  projectId?: string,
): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.put(`/api/sessions/${sessionId}/param-overrides?${params.toString()}`, { param_overrides: paramOverrides });
}