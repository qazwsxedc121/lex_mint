/**
 * Service interfaces for Chat module dependency injection
 */

import type {
  Session,
  SessionDetail,
  TokenUsage,
  CostInfo,
  SearchSource,
  UploadedFile,
  ParamOverrides,
  ContextInfo,
  CompareModelResponse
} from '../../../types/message';
import type { Assistant } from '../../../types/assistant';
import type { CapabilitiesResponse } from '../../../types/model';
import type { MutableRefObject } from 'react';

/**
 * ChatAPI - Encapsulates all backend API calls
 * This interface allows different modules to provide custom implementations
 */
export interface ChatAPI {
  // Session operations
  getSession(sessionId: string): Promise<SessionDetail>;
  createSession(modelId?: string, assistantId?: string, temporary?: boolean): Promise<string>;
  listSessions(): Promise<Session[]>;
  deleteSession(sessionId: string): Promise<void>;
  saveTemporarySession(sessionId: string): Promise<void>;
  updateSessionTitle(sessionId: string, title: string): Promise<void>;
  duplicateSession(sessionId: string): Promise<string>;
  moveSession(sessionId: string, targetContextType: string, targetProjectId?: string): Promise<void>;
  copySession(sessionId: string, targetContextType: string, targetProjectId?: string): Promise<string>;
  branchSession(sessionId: string, messageId: string): Promise<string>;
  updateSessionAssistant(sessionId: string, assistantId: string): Promise<void>;
  updateSessionParamOverrides(sessionId: string, paramOverrides: ParamOverrides): Promise<void>;

  // Message operations
  sendMessageStream(
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
    onFollowupQuestions?: (questions: string[]) => void,
    onContextInfo?: (info: ContextInfo) => void,
    onThinkingDuration?: (durationMs: number) => void
  ): Promise<void>;
  deleteMessage(sessionId: string, messageId: string): Promise<void>;
  updateMessageContent(sessionId: string, messageId: string, content: string): Promise<void>;
  insertSeparator(sessionId: string): Promise<string>;
  clearAllMessages(sessionId: string): Promise<void>;
  compressContext(
    sessionId: string,
    onChunk: (chunk: string) => void,
    onComplete: (data: { message_id: string; compressed_count: number }) => void,
    onError: (error: string) => void,
    abortControllerRef?: MutableRefObject<AbortController | null>
  ): Promise<void>;
  translateText(
    text: string,
    onChunk: (chunk: string) => void,
    onComplete: () => void,
    onError: (error: string) => void,
    targetLanguage?: string,
    modelId?: string,
    abortControllerRef?: MutableRefObject<AbortController | null>,
    useInputTargetLanguage?: boolean
  ): Promise<void>;

  // File operations
  uploadFile(sessionId: string, file: File): Promise<UploadedFile>;
  downloadFile(sessionId: string, messageIndex: number, filename: string): Promise<Blob>;

  // Assistant & model
  listAssistants(): Promise<Assistant[]>;
  getAssistant(assistantId: string): Promise<Assistant>;
  getModelCapabilities(modelId: string): Promise<CapabilitiesResponse>;
  generateTitleManually(sessionId: string): Promise<{ message: string; title: string }>;
  generateFollowups(sessionId: string): Promise<string[]>;

  // Compare operations
  sendCompareStream(
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
    }
  ): Promise<void>;
}

/**
 * ChatNavigation - Abstracts routing logic
 * This allows different modules to handle navigation differently
 */
export interface ChatNavigation {
  navigateToSession(sessionId: string): void;
  navigateToRoot(): void;
  getCurrentSessionId(): string | null;
}

/**
 * ChatContextData - Shared state across chat components
 * This provides context from parent modules (backward compatibility)
 * @deprecated Use ChatServiceContextValue instead
 */
export interface ChatContextData {
  sessions?: Session[];
  sessionTitle?: string;
  onSessionsRefresh?: () => void;
  onAssistantRefresh?: () => void;
}

/**
 * ChatServiceContextValue - Complete service context
 * Includes API, navigation, and built-in state management
 */
export interface ChatServiceContextValue {
  // API and Navigation services
  api: ChatAPI;
  navigation?: ChatNavigation;

  // Built-in Sessions state management
  sessions: Session[];
  currentSession: Session | null;
  currentSessionId: string | null;
  sessionsLoading: boolean;
  sessionsError: string | null;

  // Built-in Sessions operations
  createSession: (modelId?: string, assistantId?: string) => Promise<string>;
  createTemporarySession: () => Promise<string>;
  saveTemporarySession: (sessionId: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  refreshSessions: () => Promise<void>;

  // Backward compatibility context
  context?: ChatContextData;
}
