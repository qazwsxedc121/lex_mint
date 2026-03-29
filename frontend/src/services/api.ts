/**
 * API client for backend communication using axios.
 */

import { API_BASE } from './apiBase';
import { createWorkflowRun, type WorkflowRunStreamOptions } from './asyncRunApi';
import { api } from './apiClient';
import { consumeFlowEventResponse, postFlowEventStream } from './flowEventStreamClient';
import { asNumber, asRecord, asString, iterateSSEData, parseFlowEvent, sleep } from './flowEvents';
import type { FlowEvent } from './flowEvents';
import i18n from '../i18n';
import type { ChatRequest, ChatResponse, TokenUsage, CostInfo, UploadedFile, SearchSource, ContextInfo } from '../types/message';
export {
  createProject,
  deleteProject,
  getProject,
  getToolCatalog,
  listProjects,
  updateProject,
} from './projectApi';

export {
  createPromptTemplate,
  createWorkflow,
  deletePromptTemplate,
  deleteWorkflow,
  getPromptTemplate,
  getWorkflow,
  getWorkflowRun,
  listPromptTemplates,
  listWorkflowRuns,
  listWorkflows,
  updatePromptTemplate,
  updateWorkflow,
} from './promptWorkflowCrudApi';
export {
  createChatFolder,
  deleteChatFolder,
  listChatFolders,
  reorderChatFolder,
  updateChatFolder,
  updateSessionFolder,
} from './folderApi';
export {
  exportSession,
  generateFollowups,
  importChatGPTConversations,
  importMarkdownConversation,
  synthesizeSpeech,
} from './sessionAssetApi';
export type {
  ChatGPTImportResult,
  ChatGPTImportSessionSummary,
} from './sessionAssetApi';
export {
  checkHealth,
  downloadFile,
  uploadFile,
} from './runtimeApi';
export {
  branchSession,
  clearAllMessages,
  copySession,
  createSession,
  deleteMessage,
  deleteSession,
  duplicateSession,
  getSession,
  insertSeparator,
  listSessions,
  moveSession,
  saveTemporarySession,
  searchSessions,
  updateGroupAssistants,
  updateMessageContent,
  updateSessionAssistant,
  updateSessionModel,
  updateSessionParamOverrides,
  updateSessionTarget,
  updateSessionTitle,
} from './sessionApi';
export type { SearchResult } from './sessionApi';
export {
  cancelAsyncRun,
  createAsyncRun,
  createWorkflowRun,
  getAsyncRun,
  listAsyncRuns,
  resumeAsyncRun,
} from './asyncRunApi';
export type {
  AsyncRunKind,
  AsyncRunRecord,
  AsyncRunStatus,
  ListAsyncRunsOptions,
  WorkflowRunStreamOptions,
} from './asyncRunApi';
export {
  createModel,
  createProvider,
  deleteModel,
  deleteProvider,
  getDefaultConfig,
  getModel,
  getProvider,
  getReasoningSupportedPatterns,
  listModels,
  listProviders,
  setDefaultConfig,
  testModelConnection,
  updateModel,
  updateProvider,
} from './modelRegistryApi';
export {
  generateTitleManually,
  getSearchConfig,
  getTitleGenerationConfig,
  getWebpageConfig,
  updateSearchConfig,
  updateTitleGenerationConfig,
  updateWebpageConfig,
} from './configApi';
export type {
  SearchConfig,
  SearchConfigUpdate,
  TitleGenerationConfig,
  TitleGenerationConfigUpdate,
  WebpageConfig,
  WebpageConfigUpdate,
} from './configApi';
export {
  createAssistant,
  deleteAssistant,
  fetchProviderModels,
  getAssistant,
  getBuiltinProvider,
  getDefaultAssistant,
  getDefaultAssistantId,
  getModelCapabilities,
  listAssistants,
  listBuiltinProviders,
  listProtocols,
  listProviderEndpointProfiles,
  probeProviderEndpoints,
  setDefaultAssistant,
  testProviderConnection,
  testProviderStoredConnection,
  updateAssistant,
} from './assistantProviderApi';
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
  WorkflowFlowEvent,
  WorkflowRunCallbacks,
} from '../types/workflow';

interface FileReferenceInput {
  path: string;
  project_id: string;
}

interface UploadedFilePayload {
  filename: string;
  size: number;
  mime_type: string;
  temp_path: string;
}

interface ChatStreamRequestBody {
  session_id: string;
  message: string;
  truncate_after_index: number | null;
  skip_user_message: boolean;
  context_type: string;
  reasoning_effort?: string;
  project_id?: string;
  use_web_search?: boolean;
  attachments?: UploadedFilePayload[];
  file_references?: FileReferenceInput[];
  active_file_path?: string;
  active_file_hash?: string;
}

interface CompareStreamRequestBody {
  session_id: string;
  message: string;
  model_ids: string[];
  context_type: string;
  use_web_search: boolean;
  reasoning_effort?: string;
  project_id?: string;
  attachments?: UploadedFilePayload[];
  file_references?: FileReferenceInput[];
}

function toUploadedFilePayload(attachments: UploadedFile[]): UploadedFilePayload[] {
  return attachments.map((attachment) => ({
    filename: attachment.filename,
    size: attachment.size,
    mime_type: attachment.mime_type,
    temp_path: attachment.temp_path,
  }));
}

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
  fileReferences?: FileReferenceInput[],
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
    const requestBody: ChatStreamRequestBody = {
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
      requestBody.attachments = toUploadedFilePayload(attachments);
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
    fileReferences?: FileReferenceInput[];
  }
): Promise<void> {
  const controller = new AbortController();
  if (abortControllerRef) {
    abortControllerRef.current = controller;
  }

  try {
    const requestBody: CompareStreamRequestBody = {
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
      requestBody.attachments = toUploadedFilePayload(options.attachments);
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

export default api;
