/**
 * Default implementation of ChatAPI using existing API functions
 * This wraps the global API functions for backward compatibility
 */

import * as api from '../../../services/api';
import type { ChatAPI } from './interfaces';

export const defaultChatAPI: ChatAPI = {
  // Session operations
  getSession: api.getSession,
  createSession: api.createSession,
  listSessions: api.listSessions,
  deleteSession: api.deleteSession,
  updateSessionTitle: api.updateSessionTitle,
  duplicateSession: api.duplicateSession,
  branchSession: api.branchSession,
  updateSessionAssistant: api.updateSessionAssistant,
  updateSessionParamOverrides: api.updateSessionParamOverrides,

  // Message operations
  sendMessageStream: api.sendMessageStream,
  deleteMessage: api.deleteMessage,
  insertSeparator: api.insertSeparator,
  clearAllMessages: api.clearAllMessages,

  // File operations
  uploadFile: api.uploadFile,
  downloadFile: api.downloadFile,

  // Assistant & model
  listAssistants: api.listAssistants,
  getAssistant: api.getAssistant,
  getModelCapabilities: api.getModelCapabilities,
  generateTitleManually: api.generateTitleManually,
};
