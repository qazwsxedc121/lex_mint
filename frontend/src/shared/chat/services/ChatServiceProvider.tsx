/**
 * ChatServiceProvider - Provides services to chat components via Context
 * This enables dependency injection for API, navigation, and shared data
 *
 * Version 2.0: Built-in sessions state management
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import type { ChatAPI, ChatNavigation, ChatContextData, ChatServiceContextValue } from './interfaces';
import type { Session } from '../../../types/message';
import { defaultChatAPI } from './defaultChatAPI';

const ChatServiceContext = createContext<ChatServiceContextValue | null>(null);

export const useChatServices = () => {
  const context = useContext(ChatServiceContext);
  if (!context) {
    throw new Error('useChatServices must be used within ChatServiceProvider');
  }
  return context;
};

interface ChatServiceProviderProps {
  children: React.ReactNode;
  api?: ChatAPI;
  navigation?: ChatNavigation;
  context?: ChatContextData; // Backward compatibility
}

export const ChatServiceProvider: React.FC<ChatServiceProviderProps> = ({
  children,
  api = defaultChatAPI,
  navigation,
  context: legacyContext,
}) => {
  // Built-in Sessions state management
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  const shouldFallbackToModel = useCallback((err: unknown): boolean => {
    if (!err || typeof err !== 'object') {
      return false;
    }

    const payload = err as {
      response?: { data?: { detail?: unknown } };
      message?: string;
    };
    const detail = payload.response?.data?.detail;
    const detailText = typeof detail === 'string' ? detail : '';
    const message = (detailText || payload.message || '').toLowerCase();
    return message.includes('assistant') && message.includes('not found');
  }, []);

  // Track current session ID from navigation
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(
    navigation?.getCurrentSessionId() || null
  );

  // Load sessions on mount
  const loadSessions = useCallback(async () => {
    try {
      setSessionsLoading(true);
      setSessionsError(null);
      const data = await api.listSessions();
      setSessions(data);
    } catch (err) {
      setSessionsError(err instanceof Error ? err.message : 'Failed to load sessions');
    } finally {
      setSessionsLoading(false);
    }
  }, [api]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Update currentSessionId when navigation changes
  useEffect(() => {
    const id = navigation?.getCurrentSessionId() || null;
    setCurrentSessionId(id);
  }, [navigation]);

  // Create session operation
  const createSession = useCallback(async (
    modelId?: string,
    assistantId?: string,
    temporary: boolean = false,
    targetType?: 'assistant' | 'model'
  ): Promise<string> => {
    try {
      setSessionsError(null);
      const effectiveTargetType = targetType || (assistantId ? 'assistant' : modelId ? 'model' : 'assistant');
      let sessionId: string;
      try {
        sessionId = await api.createSession(modelId, assistantId, temporary, effectiveTargetType);
      } catch (err) {
        if (
          effectiveTargetType === 'assistant' &&
          !assistantId &&
          !targetType &&
          shouldFallbackToModel(err)
        ) {
          sessionId = await api.createSession(modelId, assistantId, temporary, 'model');
        } else {
          throw err;
        }
      }
      if (!temporary) {
        // Reload sessions to include the new one
        await loadSessions();
      }
      return sessionId;
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Failed to create session';
      setSessionsError(error);
      throw err;
    }
  }, [api, loadSessions, shouldFallbackToModel]);

  // Create temporary session operation (does not reload session list)
  const createTemporarySession = useCallback(async (): Promise<string> => {
    try {
      setSessionsError(null);
      let sessionId: string;
      try {
        sessionId = await api.createSession(undefined, undefined, true, 'assistant');
      } catch (err) {
        if (shouldFallbackToModel(err)) {
          sessionId = await api.createSession(undefined, undefined, true, 'model');
        } else {
          throw err;
        }
      }
      // Do NOT reload sessions - temp sessions are hidden from the list
      return sessionId;
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Failed to create temporary session';
      setSessionsError(error);
      throw err;
    }
  }, [api, shouldFallbackToModel]);

  // Save temporary session (convert to permanent)
  const saveTemporarySession = useCallback(async (sessionId: string): Promise<void> => {
    try {
      setSessionsError(null);
      await api.saveTemporarySession(sessionId);
      // Reload sessions so the saved session appears in the sidebar
      await loadSessions();
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Failed to save session';
      setSessionsError(error);
      throw err;
    }
  }, [api, loadSessions]);

  // Delete session operation
  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      setSessionsError(null);
      await api.deleteSession(sessionId);
      // Remove from local state
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Failed to delete session';
      setSessionsError(error);
      throw err;
    }
  }, [api]);

  // Refresh sessions operation
  const refreshSessions = useCallback(async () => {
    await loadSessions();
  }, [loadSessions]);

  // Compute current session
  const currentSession = useMemo(() => {
    if (!currentSessionId) return null;
    return sessions.find(s => s.session_id === currentSessionId) || null;
  }, [currentSessionId, sessions]);

  // Create context value
  const value: ChatServiceContextValue = useMemo(() => ({
    api,
    navigation,
    sessions,
    currentSession,
    currentSessionId,
    sessionsLoading,
    sessionsError,
    createSession,
    createTemporarySession,
    saveTemporarySession,
    deleteSession,
    refreshSessions,
    context: legacyContext,
  }), [
    api,
    navigation,
    sessions,
    currentSession,
    currentSessionId,
    sessionsLoading,
    sessionsError,
    createSession,
    createTemporarySession,
    saveTemporarySession,
    deleteSession,
    refreshSessions,
    legacyContext,
  ]);

  return (
    <ChatServiceContext.Provider value={value}>
      {children}
    </ChatServiceContext.Provider>
  );
};
