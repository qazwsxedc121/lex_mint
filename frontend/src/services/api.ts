/**
 * API client for backend communication using axios.
 */

import { API_BASE } from './apiBase';
import { api } from './apiClient';
import { consumeFlowEventResponse, postFlowEventStream } from './flowEventStreamClient';
import { asNumber, asRecord, asString, iterateSSEData, parseFlowEvent, sleep } from './flowEvents';
import type { FlowEvent } from './flowEvents';
import i18n from '../i18n';
import type { Session, SessionDetail, ChatRequest, ChatResponse, TokenUsage, CostInfo, UploadedFile, SearchSource, ParamOverrides, ContextInfo } from '../types/message';
import type {
  Provider,
  Model,
  DefaultConfig,
  BuiltinProviderInfo,
  ModelInfo,
  CapabilitiesResponse,
  ProtocolInfo,
  ProviderEndpointProbeRequest,
  ProviderEndpointProbeResponse,
  ProviderEndpointProfilesResponse,
} from '../types/model';
import type { Assistant, AssistantCreate, AssistantUpdate } from '../types/assistant';
import type { Project, ProjectCreate, ProjectUpdate } from '../types/project';
import type { PromptTemplate, PromptTemplateCreate, PromptTemplateUpdate } from '../types/promptTemplate';
import type { Folder } from '../types/folder';
export {
  createKnowledgeBase,
  deleteDocument,
  deleteKnowledgeBase,
  getKnowledgeBase,
  getRagConfig,
  listDocuments,
  listKnowledgeBaseChunks,
  listKnowledgeBases,
  reprocessDocument,
  updateKnowledgeBase,
  updateRagConfig,
  uploadDocument,
} from './knowledgeBaseApi';
import type { MutableRefObject } from 'react';
export {
  createMemory,
  deleteMemory,
  getMemorySettings,
  listMemories,
  searchMemories,
  updateMemory,
  updateMemorySettings,
} from './memoryApi';
import type {
  Workflow,
  WorkflowCreate,
  WorkflowFlowEvent,
  WorkflowRunCallbacks,
  WorkflowRunRecord,
  WorkflowUpdate,
} from '../types/workflow';

export {
  addProjectWorkspaceItem,
  applyProjectChatDiff,
  createFile,
  createFolder,
  createProjectBrowseDirectory,
  deleteFile,
  deleteFolder,
  getFileTree,
  getProjectWorkspaceState,
  listProjectBrowseRoots,
  listProjectDirectories,
  readFile,
  renameProjectPath,
  searchProjectFiles,
  searchProjectText,
  writeFile,
} from './projectFilesApi';
export type {
  ApplyProjectChatDiffRequest,
  ApplyProjectChatDiffResponse,
  FileSearchResult,
  ProjectTextSearchMatch,
  ProjectTextSearchResponse,
  ProjectWorkspaceItemType,
  ProjectWorkspaceItemUpsertRequest,
  ProjectWorkspaceRecentItem,
  ProjectWorkspaceState,
} from './projectFilesApi';
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
  targetType?: 'assistant' | 'model'
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
 * Move a session between contexts (chat/projects).
 */
export async function moveSession(
  sessionId: string,
  sourceContextType: string = 'chat',
  sourceProjectId?: string,
  targetContextType: string = 'chat',
  targetProjectId?: string
): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', sourceContextType);
  if (sourceProjectId) {
    params.append('project_id', sourceProjectId);
  }

  const body: { target_context_type: string; target_project_id?: string } = {
    target_context_type: targetContextType,
  };
  if (targetProjectId) {
    body.target_project_id = targetProjectId;
  }

  await api.post(`/api/sessions/${sessionId}/move?${params.toString()}`, body);
}

/**
 * Copy a session between contexts (chat/projects).
 */
export async function copySession(
  sessionId: string,
  sourceContextType: string = 'chat',
  sourceProjectId?: string,
  targetContextType: string = 'chat',
  targetProjectId?: string
): Promise<string> {
  const params = new URLSearchParams();
  params.append('context_type', sourceContextType);
  if (sourceProjectId) {
    params.append('project_id', sourceProjectId);
  }

  const body: { target_context_type: string; target_project_id?: string } = {
    target_context_type: targetContextType,
  };
  if (targetProjectId) {
    body.target_project_id = targetProjectId;
  }

  const response = await api.post<{ session_id: string; message: string }>(
    `/api/sessions/${sessionId}/copy?${params.toString()}`,
    body
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
 * Prompt templates CRUD
 */
export async function listPromptTemplates(): Promise<PromptTemplate[]> {
  const response = await api.get<PromptTemplate[]>('/api/prompt-templates');
  return response.data;
}

export async function getPromptTemplate(templateId: string): Promise<PromptTemplate> {
  const response = await api.get<PromptTemplate>(`/api/prompt-templates/${templateId}`);
  return response.data;
}

export async function createPromptTemplate(template: PromptTemplateCreate): Promise<void> {
  await api.post('/api/prompt-templates', template);
}

export async function updatePromptTemplate(templateId: string, template: PromptTemplateUpdate): Promise<void> {
  await api.put(`/api/prompt-templates/${templateId}`, template);
}

export async function deletePromptTemplate(templateId: string): Promise<void> {
  await api.delete(`/api/prompt-templates/${templateId}`);
}

/**
 * Workflows CRUD
 */
export async function listWorkflows(): Promise<Workflow[]> {
  const response = await api.get<Workflow[]>('/api/workflows');
  return response.data;
}

export async function getWorkflow(workflowId: string): Promise<Workflow> {
  const response = await api.get<Workflow>(`/api/workflows/${workflowId}`);
  return response.data;
}

export async function createWorkflow(workflow: WorkflowCreate): Promise<string> {
  const response = await api.post<{ id: string }>('/api/workflows', workflow);
  return response.data.id;
}

export async function updateWorkflow(workflowId: string, workflow: WorkflowUpdate): Promise<void> {
  await api.put(`/api/workflows/${workflowId}`, workflow);
}

export async function deleteWorkflow(workflowId: string): Promise<void> {
  await api.delete(`/api/workflows/${workflowId}`);
}

export async function listWorkflowRuns(workflowId: string, limit: number = 50): Promise<WorkflowRunRecord[]> {
  const response = await api.get<WorkflowRunRecord[]>(`/api/workflows/${workflowId}/runs`, {
    params: { limit },
  });
  return response.data;
}

export async function getWorkflowRun(workflowId: string, runId: string): Promise<WorkflowRunRecord> {
  const response = await api.get<WorkflowRunRecord>(`/api/workflows/${workflowId}/runs/${runId}`);
  return response.data;
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
  await postFlowEventStream({
    url: `${API_BASE}/api/chat/compress`,
    body: {
      session_id: sessionId,
      context_type: contextType,
      project_id: projectId,
    },
    abortControllerRef,
    onAbort: () => {
      console.log('Compression aborted by user');
    },
    onInvalidPayload: () => {
      onError('Invalid stream event payload: missing flow_event');
    },
    onStreamError: (message) => {
      onError(message || 'Compression stream error');
    },
    onFlowEvent: (flowEvent) => {
      if (flowEvent.event_type === 'stream_ended') {
        return 'stop';
      }

      if (flowEvent.event_type === 'compression_completed') {
        const payload = flowEvent.payload;
        onComplete({
          message_id: asString(payload.message_id) || '',
          compressed_count: asNumber(payload.compressed_count) || 0,
        });
        return 'continue';
      }

      if (flowEvent.event_type === 'text_delta') {
        const text = asString(flowEvent.payload.text) || asString(flowEvent.payload.chunk);
        if (text) {
          onChunk(text);
        }
      }

      return 'continue';
    },
  });
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
  const body: Record<string, unknown> = { text };
  if (targetLanguage) body.target_language = targetLanguage;
  if (modelId) body.model_id = modelId;
  if (useInputTargetLanguage) body.use_input_target_language = true;

  await postFlowEventStream({
    url: `${API_BASE}/api/translate`,
    body,
    abortControllerRef,
    onAbort: () => {
      console.log('Translation aborted by user');
    },
    onInvalidPayload: () => {
      onError('Invalid stream event payload: missing flow_event');
    },
    onStreamError: (message) => {
      onError(message || 'Translation stream error');
    },
    onFlowEvent: (flowEvent) => {
      if (flowEvent.event_type === 'stream_ended') {
        onComplete();
        return 'stop';
      }

      if (flowEvent.event_type === 'translation_completed' || flowEvent.event_type === 'language_detected') {
        return 'continue';
      }

      if (flowEvent.event_type === 'text_delta') {
        const textChunk = asString(flowEvent.payload.text) || asString(flowEvent.payload.chunk);
        if (textChunk) {
          onChunk(textChunk);
        }
      }

      return 'continue';
    },
  });
}

/**
 * Run a workflow and consume flow_event SSE stream.
 */
export interface WorkflowRunStreamOptions {
  sessionId?: string;
  contextType?: 'workflow' | 'chat' | 'project';
  projectId?: string;
  streamMode?: 'default' | 'editor_rewrite';
  artifactTargetPath?: string;
  writeMode?: 'none' | 'create' | 'overwrite';
}

export type AsyncRunKind = 'workflow' | 'chat';
export type AsyncRunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface AsyncRunRecord {
  run_id: string;
  stream_id: string;
  kind: AsyncRunKind;
  status: AsyncRunStatus;
  context_type: 'workflow' | 'chat' | 'project';
  project_id?: string | null;
  session_id?: string | null;
  workflow_id?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  request_payload: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  error?: string | null;
  last_event_id?: string | null;
  last_seq: number;
}

export interface ListAsyncRunsOptions {
  limit?: number;
  kind?: AsyncRunKind;
  status?: AsyncRunStatus;
  contextType?: 'workflow' | 'chat' | 'project';
  projectId?: string;
  sessionId?: string;
  workflowId?: string;
}

interface AsyncRunListResponse {
  runs: AsyncRunRecord[];
}

function extractErrorDetail(payload: unknown): string | null {
  const data = asRecord(payload);
  if (!data) {
    return null;
  }
  const detail = data.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  const detailRecord = asRecord(detail);
  const detailMessage = detailRecord ? asString(detailRecord.message) : undefined;
  if (detailMessage && detailMessage.trim()) {
    return detailMessage;
  }
  return null;
}

async function getResponseErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json();
    return extractErrorDetail(payload) || fallback;
  } catch {
    return fallback;
  }
}

export async function createAsyncRun(payload: {
  kind: AsyncRunKind;
  workflow_id?: string;
  inputs?: Record<string, unknown>;
  session_id?: string;
  context_type?: 'workflow' | 'chat' | 'project';
  project_id?: string;
  stream_mode?: 'default' | 'editor_rewrite';
  artifact_target_path?: string;
  write_mode?: 'none' | 'create' | 'overwrite';
}): Promise<AsyncRunRecord> {
  const response = await api.post<AsyncRunRecord>('/api/runs', payload);
  return response.data;
}

export async function createWorkflowRun(
  workflowId: string,
  inputs: Record<string, unknown>,
  options?: WorkflowRunStreamOptions,
): Promise<AsyncRunRecord> {
  return createAsyncRun({
    kind: 'workflow',
    workflow_id: workflowId,
    inputs,
    session_id: options?.sessionId,
    context_type: options?.contextType || 'workflow',
    project_id: options?.projectId,
    stream_mode: options?.streamMode || 'default',
    artifact_target_path: options?.artifactTargetPath,
    write_mode: options?.writeMode,
  });
}

export async function listAsyncRuns(options?: ListAsyncRunsOptions): Promise<AsyncRunRecord[]> {
  const response = await api.get<AsyncRunListResponse>('/api/runs', {
    params: {
      limit: options?.limit ?? 50,
      kind: options?.kind,
      status: options?.status,
      context_type: options?.contextType,
      project_id: options?.projectId,
      session_id: options?.sessionId,
      workflow_id: options?.workflowId,
    },
  });
  return response.data.runs;
}

export async function getAsyncRun(runId: string): Promise<AsyncRunRecord> {
  const response = await api.get<AsyncRunRecord>(`/api/runs/${runId}`);
  return response.data;
}

export async function cancelAsyncRun(runId: string): Promise<AsyncRunRecord> {
  const response = await api.post<AsyncRunRecord>(`/api/runs/${runId}/cancel`);
  return response.data;
}

export async function runWorkflowStream(
  workflowId: string,
  inputs: Record<string, unknown>,
  callbacks: WorkflowRunCallbacks,
  abortControllerRef?: MutableRefObject<AbortController | null>,
  options?: WorkflowRunStreamOptions,
): Promise<void> {
  const controller = new AbortController();
  if (abortControllerRef) {
    abortControllerRef.current = controller;
  }

  try {
    const run = await createWorkflowRun(workflowId, inputs, options);
    callbacks.onRunCreated?.(run.run_id);

    let lastEventId: string | undefined;
    let resumeAttempts = 0;
    const resumeDelaysMs = [500, 1500];

    const consumeResponse = async (response: Response): Promise<'done' | 'disconnected'> => {
      let streamFinished = false;
      try {
        await consumeFlowEventResponse({
          response,
          onInvalidPayload: () => {
            callbacks.onError?.(i18n.t('workflow:errors.runStreamInvalidPayload'));
            streamFinished = true;
          },
          onStreamError: (message) => {
            callbacks.onError?.(message || i18n.t('workflow:errors.runFailed'));
            streamFinished = true;
          },
          onFlowEvent: (flowEvent) => {
            lastEventId = flowEvent.event_id;
            const workflowEvent = flowEvent as WorkflowFlowEvent;
            callbacks.onEvent?.(workflowEvent);

            if (workflowEvent.event_type === 'text_delta') {
              const textChunk = asString(workflowEvent.payload.text) || asString(workflowEvent.payload.chunk);
              if (textChunk) {
                callbacks.onChunk?.(textChunk, workflowEvent);
              }
              return 'continue';
            }

            if (workflowEvent.event_type === 'stream_ended') {
              callbacks.onComplete?.();
              streamFinished = true;
              return 'stop';
            }

            return 'continue';
          },
        });
        return streamFinished ? 'done' : 'disconnected';
      } catch (streamError: unknown) {
        if (streamError instanceof Error && streamError.name === 'AbortError') {
          throw streamError;
        }
        return 'disconnected';
      }
    };

    let response = await fetch(`${API_BASE}/api/runs/${run.run_id}/stream`, {
      method: 'GET',
      signal: controller.signal,
    });

    if (!response.ok) {
      const message = await getResponseErrorMessage(
        response,
        `Failed to open workflow stream: ${response.status}`
      );
      throw new Error(message);
    }

    while (true) {
      const status = await consumeResponse(response);
      if (status === 'done') {
        return;
      }

      if (!lastEventId) {
        callbacks.onError?.(i18n.t('workflow:errors.runStreamInvalidPayload'));
        return;
      }

      if (resumeAttempts >= resumeDelaysMs.length) {
        callbacks.onError?.('Workflow stream disconnected and resume retries were exhausted.');
        return;
      }

      await sleep(resumeDelaysMs[resumeAttempts]);
      resumeAttempts += 1;

      response = await fetch(`${API_BASE}/api/runs/${run.run_id}/stream/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ last_event_id: lastEventId }),
        signal: controller.signal,
      });

      if (response.status === 410) {
        callbacks.onError?.('Workflow stream resume cursor expired. Please run again.');
        return;
      }
      if (response.status === 404) {
        callbacks.onError?.('Workflow stream not found.');
        return;
      }
      if (response.status === 409) {
        callbacks.onError?.('Workflow stream context mismatch. Please run again.');
        return;
      }
      if (!response.ok) {
        const message = await getResponseErrorMessage(
          response,
          `Workflow resume stream failed: ${response.status}`
        );
        throw new Error(message);
      }
    }
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') {
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
  onThinkingDuration?: (durationMs: number) => void,
  fileReferences?: Array<{ path: string; project_id: string }>,
  onToolCalls?: (calls: Array<{ id?: string; name: string; args: Record<string, unknown> }>) => void,
  onToolResults?: (results: Array<{ name: string; result: string; tool_call_id: string }>) => void,
  onAssistantStart?: (assistantId: string, name: string, icon?: string) => void,
  onAssistantDone?: (assistantId: string) => void,
  onGroupEvent?: (event: {
    type: string;
    assistant_id?: string;
    assistant_turn_id?: string;
    assistant_ids?: string[];
    assistant_names?: string[];
    name?: string;
    icon?: string;
    chunk?: string;
    message_id?: string;
    round?: number;
    max_rounds?: number;
    action?: string;
    reason?: string;
    supervisor_id?: string;
    supervisor_name?: string;
    rounds?: number;
    usage?: TokenUsage;
    cost?: CostInfo;
    sources?: SearchSource[];
    duration_ms?: number;
    [key: string]: unknown;
  }) => void,
  activeFilePath?: string,
  activeFileHash?: string,
): Promise<void> {
  // Create AbortController for cancellation support
  const controller = new AbortController();
  if (abortControllerRef) {
    abortControllerRef.current = controller;
  }

  type FlowHandleResult = 'handled' | 'return' | 'unhandled';

  const handleFlowEvent = (flowEvent: FlowEvent): FlowHandleResult => {
    const payload = flowEvent.payload || {};
    const assistantId = asString(payload.assistant_id);
    const assistantTurnId = asString(payload.assistant_turn_id) || flowEvent.turn_id;
    const name = asString(payload.name);
    const icon = asString(payload.icon);

    switch (flowEvent.event_type) {
      case 'stream_ended':
        onDone();
        return 'return';
      case 'stream_error':
        onError(asString(payload.error) || 'Stream error');
        return 'return';
      case 'text_delta': {
        const chunk = asString(payload.text) || asString(payload.chunk);
        if (!chunk) {
          return 'handled';
        }
        if ((assistantId || assistantTurnId) && onGroupEvent) {
          onGroupEvent({
            type: 'assistant_chunk',
            assistant_id: assistantId,
            assistant_turn_id: assistantTurnId,
            chunk,
          });
          return 'handled';
        }
        onChunk(chunk);
        return 'handled';
      }
      case 'usage_reported': {
        const usage = payload.usage as TokenUsage | undefined;
        const cost = payload.cost as CostInfo | undefined;
        if (usage && onUsage) {
          onUsage(usage, cost);
        }
        if (onGroupEvent && (assistantId || assistantTurnId)) {
          onGroupEvent({
            type: 'usage',
            assistant_id: assistantId,
            assistant_turn_id: assistantTurnId,
            usage,
            cost,
          });
        }
        return 'handled';
      }
      case 'sources_reported': {
        const sources = payload.sources as SearchSource[] | undefined;
        if (sources && onSources) {
          onSources(sources);
        }
        if (onGroupEvent && (assistantId || assistantTurnId)) {
          onGroupEvent({
            type: 'sources',
            assistant_id: assistantId,
            assistant_turn_id: assistantTurnId,
            sources,
          });
        }
        return 'handled';
      }
      case 'context_reported': {
        if (onContextInfo) {
          onContextInfo(payload as unknown as ContextInfo);
        }
        return 'handled';
      }
      case 'reasoning_duration_reported': {
        const durationMs = asNumber(payload.duration_ms);
        if (durationMs !== undefined && onThinkingDuration) {
          onThinkingDuration(durationMs);
        }
        if (onGroupEvent && (assistantId || assistantTurnId)) {
          onGroupEvent({
            type: 'thinking_duration',
            assistant_id: assistantId,
            assistant_turn_id: assistantTurnId,
            duration_ms: durationMs,
          });
        }
        return 'handled';
      }
      case 'tool_call_started': {
        const calls = payload.calls as Array<{ id?: string; name: string; args: Record<string, unknown> }> | undefined;
        if (calls && onToolCalls) {
          onToolCalls(calls);
        }
        return 'handled';
      }
      case 'tool_call_finished': {
        const results = payload.results as Array<{ name: string; result: string; tool_call_id: string }> | undefined;
        if (results && onToolResults) {
          onToolResults(results);
        }
        return 'handled';
      }
      case 'user_message_identified': {
        const messageId = asString(payload.message_id);
        if (messageId && onUserMessageId) {
          onUserMessageId(messageId);
        }
        return 'handled';
      }
      case 'assistant_message_identified': {
        const messageId = asString(payload.message_id);
        if (messageId && onAssistantMessageId) {
          onAssistantMessageId(messageId);
        }
        if (onGroupEvent && (assistantId || assistantTurnId || messageId)) {
          onGroupEvent({
            type: 'assistant_message_id',
            assistant_id: assistantId,
            assistant_turn_id: assistantTurnId,
            message_id: messageId,
          });
        }
        return 'handled';
      }
      case 'assistant_turn_started': {
        if (onGroupEvent) {
          onGroupEvent({
            type: 'assistant_start',
            assistant_id: assistantId,
            assistant_turn_id: assistantTurnId,
            name,
            icon,
          });
        } else if (assistantId && name && onAssistantStart) {
          onAssistantStart(assistantId, name, icon);
        }
        return 'handled';
      }
      case 'assistant_turn_finished': {
        if (onGroupEvent) {
          onGroupEvent({
            type: 'assistant_done',
            assistant_id: assistantId,
            assistant_turn_id: assistantTurnId,
          });
        } else if (assistantId && onAssistantDone) {
          onAssistantDone(assistantId);
        }
        return 'handled';
      }
      case 'group_round_started':
      case 'group_action_reported':
      case 'group_done_reported': {
        if (!onGroupEvent) {
          return 'handled';
        }
        const mappedType =
          flowEvent.event_type === 'group_round_started'
            ? 'group_round_start'
            : flowEvent.event_type === 'group_action_reported'
              ? 'group_action'
              : 'group_done';
        onGroupEvent({
          type: mappedType,
          ...payload,
        });
        return 'handled';
      }
      case 'followup_questions_reported': {
        const questions = payload.questions;
        if (Array.isArray(questions) && onFollowupQuestions) {
          onFollowupQuestions(questions.filter((item): item is string => typeof item === 'string'));
        }
        return 'handled';
      }
      case 'stream_started':
      case 'resume_started':
      case 'replay_finished':
        return 'handled';
      default:
        return 'unhandled';
    }
  };

  try {
    const requestBody: any = {
      session_id: sessionId,
      message,
      truncate_after_index: truncateAfterIndex,
      skip_user_message: skipUserMessage,
      context_type: contextType,
    };

    if (reasoningEffort !== undefined && reasoningEffort !== '') {
      requestBody.reasoning_effort = reasoningEffort;
    }

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

    if (fileReferences && fileReferences.length > 0) {
      requestBody.file_references = fileReferences;
    }

    if (activeFilePath) {
      requestBody.active_file_path = activeFilePath;
    }
    if (activeFileHash) {
      requestBody.active_file_hash = activeFileHash;
    }

    let activeStreamId: string | undefined;
    let lastEventId: string | undefined;
    let resumeAttempts = 0;
    const resumeDelaysMs = [500, 1500];

    const consumeResponse = async (response: Response): Promise<'done' | 'disconnected'> => {
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Response body is not readable');
      }

      try {
        try {
          for await (const dataStr of iterateSSEData(reader)) {
            try {
              const data = JSON.parse(dataStr);
              const flowEvent = parseFlowEvent(data.flow_event);
              if (!flowEvent) {
                onError('Invalid stream event payload: missing flow_event');
                return 'done';
              }

              activeStreamId = flowEvent.stream_id;
              lastEventId = flowEvent.event_id;

              const handleResult = handleFlowEvent(flowEvent);
              if (handleResult === 'return') {
                return 'done';
              }
              if (handleResult === 'handled') {
                continue;
              }
            } catch {
              // Ignore malformed SSE event payloads.
              continue;
            }
          }
          return 'disconnected';
        } catch (streamError: unknown) {
          if (streamError instanceof Error && streamError.name === 'AbortError') {
            throw streamError;
          }
          return 'disconnected';
        }
      } finally {
        reader.releaseLock();
      }
    };

    const openInitialStream = async (): Promise<Response> => {
      return fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
        signal: controller.signal,
      });
    };

    const openResumeStream = async (): Promise<Response> => {
      if (!activeStreamId || !lastEventId) {
        throw new Error('Resume cursor is unavailable');
      }
      return fetch(`${API_BASE}/api/chat/stream/resume`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          stream_id: activeStreamId,
          last_event_id: lastEventId,
          context_type: contextType,
          project_id: projectId,
        }),
        signal: controller.signal,
      });
    };

    let response = await openInitialStream();
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    while (true) {
      const status = await consumeResponse(response);
      if (status === 'done') {
        return;
      }

      if (!activeStreamId || !lastEventId) {
        throw new Error('Stream disconnected before flow_event cursor was available');
      }

      if (resumeAttempts >= resumeDelaysMs.length) {
        throw new Error('Stream disconnected and resume retries were exhausted');
      }

      await sleep(resumeDelaysMs[resumeAttempts]);
      resumeAttempts += 1;

      response = await openResumeStream();
      if (response.status === 410) {
        onError('Stream resume cursor expired, please resend your message.');
        return;
      }
      if (response.status === 404) {
        onError('Stream not found for resume.');
        return;
      }
      if (response.status === 409) {
        onError('Stream context mismatch, please resend your message.');
        return;
      }
      if (!response.ok) {
        throw new Error(`Resume stream failed: ${response.status}`);
      }
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
 * Send a compare request to stream responses from multiple models.
 */
export async function sendCompareStream(
  sessionId: string,
  message: string,
  modelIds: string[],
  callbacks: {
    onModelChunk: (modelId: string, chunk: string) => void;
    onModelStart: (modelId: string, modelName: string) => void;
    onModelDone: (modelId: string, content: string, usage?: TokenUsage, cost?: CostInfo) => void;
    onModelError: (modelId: string, error: string) => void;
    onUserMessageId: (messageId: string) => void;
    onAssistantMessageId: (messageId: string) => void;
    onSources?: (sources: SearchSource[]) => void;
    onDone: () => void;
    onError: (error: string) => void;
  },
  abortControllerRef?: MutableRefObject<AbortController | null>,
  options?: {
    reasoningEffort?: string;
    attachments?: UploadedFile[];
    useWebSearch?: boolean;
    contextType?: string;
    projectId?: string;
    fileReferences?: Array<{ path: string; project_id: string }>;
  }
): Promise<void> {
  const controller = new AbortController();
  if (abortControllerRef) {
    abortControllerRef.current = controller;
  }

  try {
    const requestBody: any = {
      session_id: sessionId,
      message,
      model_ids: modelIds,
      context_type: options?.contextType || 'chat',
      use_web_search: options?.useWebSearch || false,
    };

    if (options?.reasoningEffort !== undefined && options.reasoningEffort !== '') {
      requestBody.reasoning_effort = options.reasoningEffort;
    }

    if (options?.projectId) {
      requestBody.project_id = options.projectId;
    }

    if (options?.attachments && options.attachments.length > 0) {
      requestBody.attachments = options.attachments.map(a => ({
        filename: a.filename,
        size: a.size,
        mime_type: a.mime_type,
        temp_path: a.temp_path,
      }));
    }

    if (options?.fileReferences && options.fileReferences.length > 0) {
      requestBody.file_references = options.fileReferences;
    }

    const response = await fetch(`${API_BASE}/api/chat/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();

    if (!reader) {
      throw new Error('Response body is not readable');
    }

    try {
      for await (const dataStr of iterateSSEData(reader)) {
        try {
          const data = JSON.parse(dataStr);
          const flowEvent = parseFlowEvent(data.flow_event);
          if (!flowEvent) {
            callbacks.onError('Invalid compare stream event payload: missing flow_event');
            return;
          }
          const payload = flowEvent.payload;

          if (flowEvent.event_type === 'stream_error') {
            callbacks.onError(asString(payload.error) || 'Compare stream error');
            return;
          }

          if (flowEvent.event_type === 'stream_ended') {
            callbacks.onDone();
            return;
          }

          if (flowEvent.event_type === 'compare_model_started') {
            const modelId = asString(payload.model_id);
            if (!modelId) {
              continue;
            }
            callbacks.onModelStart(modelId, asString(payload.model_name) || modelId);
            continue;
          }

          if (flowEvent.event_type === 'text_delta') {
            const modelId = asString(payload.model_id);
            const text = asString(payload.text) || asString(payload.chunk);
            if (!modelId || !text) {
              continue;
            }
            callbacks.onModelChunk(modelId, text);
            continue;
          }

          if (flowEvent.event_type === 'compare_model_finished') {
            const modelId = asString(payload.model_id);
            if (!modelId) {
              continue;
            }
            callbacks.onModelDone(
              modelId,
              asString(payload.content) || '',
              payload.usage as TokenUsage | undefined,
              payload.cost as CostInfo | undefined
            );
            continue;
          }

          if (flowEvent.event_type === 'compare_model_failed') {
            const modelId = asString(payload.model_id);
            if (!modelId) {
              continue;
            }
            callbacks.onModelError(modelId, asString(payload.error) || 'Model compare failed');
            continue;
          }

          if (flowEvent.event_type === 'user_message_identified') {
            const messageId = asString(payload.message_id);
            if (messageId) {
              callbacks.onUserMessageId(messageId);
            }
            continue;
          }

          if (flowEvent.event_type === 'assistant_message_identified') {
            const messageId = asString(payload.message_id);
            if (messageId) {
              callbacks.onAssistantMessageId(messageId);
            }
            continue;
          }

          if (flowEvent.event_type === 'sources_reported' && callbacks.onSources) {
            const sources = payload.sources as SearchSource[] | undefined;
            if (sources) {
              callbacks.onSources(sources);
            }
            continue;
          }
        } catch {
          // Ignore malformed SSE event payloads.
          continue;
        }
      }
    } finally {
      reader.releaseLock();
    }
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') {
      console.log('Compare stream aborted by user');
      callbacks.onDone();
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
export async function listProviders(enabledOnly: boolean = false): Promise<Provider[]> {
  const url = enabledOnly
    ? '/api/models/providers?enabled_only=true'
    : '/api/models/providers';
  const response = await api.get<Provider[]>(url);
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
export async function listModels(providerId?: string, enabledOnly: boolean = false): Promise<Model[]> {
  const params = new URLSearchParams();
  if (providerId) {
    params.append('provider_id', providerId);
  }
  if (enabledOnly) {
    params.append('enabled_only', 'true');
  }
  const suffix = params.toString();
  const url = suffix ? `/api/models/list?${suffix}` : '/api/models/list';
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
 * Update session target (assistant or model).
 */
export async function updateSessionTarget(
  sessionId: string,
  targetType: 'assistant' | 'model',
  contextType: string = 'chat',
  projectId?: string,
  options?: { assistantId?: string; modelId?: string }
): Promise<void> {
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
  projectId?: string
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
export async function listAssistants(enabledOnly: boolean = false): Promise<Assistant[]> {
  const url = enabledOnly
    ? '/api/assistants?enabled_only=true'
    : '/api/assistants';
  const response = await api.get<Assistant[]>(url);
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
  providerId?: string,
  modelId?: string
): Promise<{ success: boolean; message: string }> {
  const response = await api.post<{ success: boolean; message: string }>(
    '/api/models/providers/test',
    {
      base_url: baseUrl,
      api_key: apiKey,
      provider_id: providerId,
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
  modelId?: string
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

/**
 * Probe provider endpoints (auto/manual diagnostics).
 */
export async function probeProviderEndpoints(
  providerId: string,
  payload: ProviderEndpointProbeRequest
): Promise<ProviderEndpointProbeResponse> {
  const response = await api.post<ProviderEndpointProbeResponse>(
    `/api/models/providers/${providerId}/probe-endpoints`,
    payload
  );
  return response.data;
}

/**
 * List endpoint profiles for a provider.
 */
export async function listProviderEndpointProfiles(
  providerId: string,
  clientRegionHint: 'cn' | 'global' | 'unknown' = 'unknown'
): Promise<ProviderEndpointProfilesResponse> {
  const response = await api.get<ProviderEndpointProfilesResponse>(
    `/api/models/providers/${providerId}/endpoint-profiles?client_region_hint=${clientRegionHint}`
  );
  return response.data;
}


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

// ==================== Folder API ====================

/**
 * List all chat folders.
 */
export async function listChatFolders(): Promise<Folder[]> {
  const response = await api.get<Folder[]>('/api/folders');
  return response.data;
}

/**
 * Create a new chat folder.
 */
export async function createChatFolder(name: string): Promise<Folder> {
  const response = await api.post<Folder>('/api/folders', { name });
  return response.data;
}

/**
 * Update chat folder name.
 */
export async function updateChatFolder(folderId: string, name: string): Promise<Folder> {
  const response = await api.put<Folder>(`/api/folders/${folderId}`, { name });
  return response.data;
}

/**
 * Delete a chat folder.
 * Sessions in this folder will be moved to ungrouped.
 */
export async function deleteChatFolder(folderId: string): Promise<void> {
  await api.delete(`/api/folders/${folderId}`);
}

/**
 * Reorder a chat folder to a new position.
 */
export async function reorderChatFolder(folderId: string, newOrder: number): Promise<Folder> {
  const response = await api.patch<Folder>(`/api/folders/${folderId}/order`, { order: newOrder });
  return response.data;
}

/**
 * Update session's folder assignment.
 */
export async function updateSessionFolder(
  sessionId: string,
  folderId: string | null,
  contextType: string = 'chat',
  projectId?: string
): Promise<void> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  await api.put(`/api/sessions/${sessionId}/folder?${params.toString()}`, { folder_id: folderId });
}
