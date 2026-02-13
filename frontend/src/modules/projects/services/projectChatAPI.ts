/**
 * Project-specific ChatAPI implementation
 * Automatically passes context_type=project and project_id to all API calls
 */

import * as api from '../../../services/api';
import type { ChatAPI } from '../../../shared/chat';

/**
 * Creates a project-specific ChatAPI instance
 * All methods automatically include context_type=project and the specified project_id
 *
 * @param projectId - The ID of the project this chat is associated with
 * @returns A ChatAPI instance configured for the project
 */
export const createProjectChatAPI = (projectId: string): ChatAPI => {
  const contextType = 'project';

  return {
    // Session operations
    getSession: async (sessionId: string) => {
      return api.getSession(sessionId, contextType, projectId);
    },

    createSession: async (modelId?: string, assistantId?: string, temporary?: boolean) => {
      return api.createSession(modelId, assistantId, contextType, projectId, temporary || false);
    },

    listSessions: async () => {
      return api.listSessions(contextType, projectId);
    },

    deleteSession: async (sessionId: string) => {
      return api.deleteSession(sessionId, contextType, projectId);
    },

    saveTemporarySession: async (sessionId: string) => {
      return api.saveTemporarySession(sessionId, contextType, projectId);
    },

    updateSessionTitle: async (sessionId: string, title: string) => {
      return api.updateSessionTitle(sessionId, title, contextType, projectId);
    },

    duplicateSession: async (sessionId: string) => {
      return api.duplicateSession(sessionId, contextType, projectId);
    },

    moveSession: async (sessionId: string, targetContextType: string, targetProjectId?: string) => {
      return api.moveSession(sessionId, contextType, projectId, targetContextType, targetProjectId);
    },

    copySession: async (sessionId: string, targetContextType: string, targetProjectId?: string) => {
      return api.copySession(sessionId, contextType, projectId, targetContextType, targetProjectId);
    },

    branchSession: async (sessionId: string, messageId: string) => {
      return api.branchSession(sessionId, messageId, contextType, projectId);
    },

    updateSessionAssistant: async (sessionId: string, assistantId: string) => {
      return api.updateSessionAssistant(sessionId, assistantId, contextType, projectId);
    },

    updateSessionParamOverrides: async (sessionId: string, paramOverrides) => {
      return api.updateSessionParamOverrides(sessionId, paramOverrides, contextType, projectId);
    },

    // Message operations
    sendMessageStream: async (
      sessionId: string,
      message: string,
      truncateAfterIndex: number | null,
      skipUserMessage: boolean,
      onChunk: (chunk: string) => void,
      onDone: () => void,
      onError: (error: string) => void,
      abortControllerRef?,
      reasoningEffort?,
      onUsage?,
      onSources?,
      attachments?,
      onUserMessageId?,
      onAssistantMessageId?,
      useWebSearch?,
      onFollowupQuestions?,
      onContextInfo?,
      onThinkingDuration?,
      fileReferences?
    ) => {
      return api.sendMessageStream(
        sessionId,
        message,
        truncateAfterIndex,
        skipUserMessage,
        onChunk,
        onDone,
        onError,
        abortControllerRef,
        reasoningEffort,
        onUsage,
        onSources,
        attachments,
        onUserMessageId,
        onAssistantMessageId,
        useWebSearch,
        contextType,
        projectId,
        onFollowupQuestions,
        onContextInfo,
        onThinkingDuration,
        fileReferences
      );
    },

    deleteMessage: async (sessionId: string, messageId: string) => {
      return api.deleteMessage(sessionId, messageId, contextType, projectId);
    },

    updateMessageContent: async (sessionId: string, messageId: string, content: string) => {
      return api.updateMessageContent(sessionId, messageId, content, contextType, projectId);
    },

    insertSeparator: async (sessionId: string) => {
      return api.insertSeparator(sessionId, contextType, projectId);
    },

    clearAllMessages: async (sessionId: string) => {
      return api.clearAllMessages(sessionId, contextType, projectId);
    },

    compressContext: async (sessionId, onChunk, onComplete, onError, abortControllerRef?) => {
      return api.compressContext(
        sessionId, onChunk, onComplete, onError,
        contextType, projectId, abortControllerRef
      );
    },

    translateText: async (text, onChunk, onComplete, onError, targetLanguage?, modelId?, abortControllerRef?, useInputTargetLanguage?) => {
      return api.translateText(
        text, onChunk, onComplete, onError,
        targetLanguage, modelId, abortControllerRef, useInputTargetLanguage
      );
    },

    // File operations
    uploadFile: async (sessionId: string, file: File) => {
      return api.uploadFile(sessionId, file, contextType, projectId);
    },

    downloadFile: async (sessionId: string, messageIndex: number, filename: string) => {
      return api.downloadFile(sessionId, messageIndex, filename);
    },

    // Assistant & model
    listAssistants: api.listAssistants,
    getAssistant: api.getAssistant,
    getModelCapabilities: api.getModelCapabilities,

    generateTitleManually: async (sessionId: string) => {
      return api.generateTitleManually(sessionId, contextType, projectId);
    },

    generateFollowups: async (sessionId: string) => {
      return api.generateFollowups(sessionId, contextType, projectId);
    },

    // Compare operations
    sendCompareStream: async (sessionId, message, modelIds, callbacks, abortControllerRef?, options?) => {
      return api.sendCompareStream(
        sessionId, message, modelIds, callbacks, abortControllerRef,
        { ...options, contextType, projectId }
      );
    },
  };
};
