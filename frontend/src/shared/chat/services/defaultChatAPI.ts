/**
 * Default implementation of ChatAPI using existing API functions
 * This wraps the global API functions for backward compatibility
 */

import * as api from '../../../services/api';
import type { ChatAPI } from './interfaces';

export const defaultChatAPI: ChatAPI = {
  getChatInputCapabilities: async () => {
    const catalog = await api.getToolCatalog();
    return Array.isArray(catalog.chat_capabilities) ? catalog.chat_capabilities : [];
  },
  // Session operations
  getSession: api.getSession,
  createSession: (modelId?: string, assistantId?: string, temporary?: boolean, targetType?: 'assistant' | 'model') =>
    api.createSession(modelId, assistantId, 'chat', undefined, temporary || false, undefined, undefined, undefined, targetType),
  createGroupSession: (groupAssistants: string[], mode, groupSettings) =>
    api.createSession(undefined, undefined, 'chat', undefined, false, groupAssistants, mode, groupSettings),
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
  updateSessionTarget: (sessionId: string, targetType: 'assistant' | 'model', options?: { assistantId?: string; modelId?: string }) =>
    api.updateSessionTarget(sessionId, targetType, 'chat', undefined, options),
  updateGroupAssistants: api.updateGroupAssistants,
  updateSessionParamOverrides: api.updateSessionParamOverrides,
  submitToolResult: api.submitChatToolResult,

  // Message operations
  sendMessageStream: async (
    sessionId, message, truncateAfterIndex, skipUserMessage,
    onChunk, onDone, onError,
    abortControllerRef?, reasoningEffort?, onUsage?, onSources?,
    attachments?, onUserMessageId?, onAssistantMessageId?,
    contextCapabilities?, contextCapabilityArgs?, onFollowupQuestions?, onContextInfo?, onThinkingDuration?, fileReferences?,
    onToolCalls?, onToolResults?,
    onAssistantStart?, onAssistantDone?, onGroupEvent?,
    activeFilePath?, activeFileHash?, temporaryTurn?
  ) => {
    return api.sendMessageStream(
      sessionId, message, truncateAfterIndex, skipUserMessage,
      onChunk, onDone, onError,
      abortControllerRef, reasoningEffort, onUsage, onSources,
      attachments, onUserMessageId, onAssistantMessageId,
      contextCapabilities,
      contextCapabilityArgs,
      'chat',       // contextType
      undefined,    // projectId
      onFollowupQuestions,
      onContextInfo,
      onThinkingDuration,
      fileReferences,
      onToolCalls,
      onToolResults,
      onAssistantStart,
      onAssistantDone,
      onGroupEvent,
      activeFilePath,
      activeFileHash,
      temporaryTurn
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
  listAssistants: (enabledOnly?: boolean) => api.listAssistants(enabledOnly),
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
