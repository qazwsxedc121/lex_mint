/**
 * Default implementation of ChatAPI using existing API functions
 * This wraps the global API functions for backward compatibility
 */

import * as api from '../../../services/api';
import type { ChatAPI } from './interfaces';

export const defaultChatAPI: ChatAPI = {
  // Session operations
  getSession: api.getSession,
  createSession: (modelId?: string, assistantId?: string, temporary?: boolean) =>
    api.createSession(modelId, assistantId, 'chat', undefined, temporary || false),
  listSessions: api.listSessions,
  deleteSession: api.deleteSession,
  saveTemporarySession: api.saveTemporarySession,
  updateSessionTitle: api.updateSessionTitle,
  duplicateSession: api.duplicateSession,
  moveSession: (sessionId: string, targetContextType: string, targetProjectId?: string) =>
    api.moveSession(sessionId, 'chat', undefined, targetContextType, targetProjectId),
  copySession: (sessionId: string, targetContextType: string, targetProjectId?: string) =>
    api.copySession(sessionId, 'chat', undefined, targetContextType, targetProjectId),
  branchSession: api.branchSession,
  updateSessionAssistant: api.updateSessionAssistant,
  updateSessionParamOverrides: api.updateSessionParamOverrides,

  // Message operations
  sendMessageStream: async (
    sessionId, message, truncateAfterIndex, skipUserMessage,
    onChunk, onDone, onError,
    abortControllerRef?, reasoningEffort?, onUsage?, onSources?,
    attachments?, onUserMessageId?, onAssistantMessageId?,
    useWebSearch?, onFollowupQuestions?, onContextInfo?, onThinkingDuration?
  ) => {
    return api.sendMessageStream(
      sessionId, message, truncateAfterIndex, skipUserMessage,
      onChunk, onDone, onError,
      abortControllerRef, reasoningEffort, onUsage, onSources,
      attachments, onUserMessageId, onAssistantMessageId,
      useWebSearch,
      'chat',       // contextType
      undefined,    // projectId
      onFollowupQuestions,
      onContextInfo,
      onThinkingDuration
    );
  },
  deleteMessage: api.deleteMessage,
  updateMessageContent: api.updateMessageContent,
  insertSeparator: api.insertSeparator,
  clearAllMessages: api.clearAllMessages,
  compressContext: async (sessionId, onChunk, onComplete, onError, abortControllerRef?) => {
    return api.compressContext(
      sessionId, onChunk, onComplete, onError,
      'chat', undefined, abortControllerRef
    );
  },
  translateText: async (text, onChunk, onComplete, onError, targetLanguage?, modelId?, abortControllerRef?, useInputTargetLanguage?) => {
    return api.translateText(
      text, onChunk, onComplete, onError,
      targetLanguage, modelId, abortControllerRef, useInputTargetLanguage
    );
  },

  // File operations
  uploadFile: api.uploadFile,
  downloadFile: api.downloadFile,

  // Assistant & model
  listAssistants: api.listAssistants,
  getAssistant: api.getAssistant,
  getModelCapabilities: api.getModelCapabilities,
  generateTitleManually: api.generateTitleManually,
  generateFollowups: api.generateFollowups,

  // Compare operations
  sendCompareStream: async (sessionId, message, modelIds, callbacks, abortControllerRef?, options?) => {
    return api.sendCompareStream(
      sessionId, message, modelIds, callbacks, abortControllerRef,
      { ...options, contextType: 'chat', projectId: undefined }
    );
  },
};
