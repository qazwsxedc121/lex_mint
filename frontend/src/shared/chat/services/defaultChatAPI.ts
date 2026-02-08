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

  // File operations
  uploadFile: api.uploadFile,
  downloadFile: api.downloadFile,

  // Assistant & model
  listAssistants: api.listAssistants,
  getAssistant: api.getAssistant,
  getModelCapabilities: api.getModelCapabilities,
  generateTitleManually: api.generateTitleManually,
};
