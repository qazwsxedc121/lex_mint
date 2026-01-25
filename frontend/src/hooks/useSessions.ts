/**
 * Custom hook for managing conversation sessions.
 */

import { useState, useEffect, useCallback } from 'react';
import type { Session } from '../types/message';
import {
  createSession as apiCreateSession,
  listSessions as apiListSessions,
  deleteSession as apiDeleteSession,
} from '../services/api';

export function useSessions() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load sessions on mount
  const loadSessions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiListSessions();
      setSessions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sessions');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const createSession = async (): Promise<string> => {
    try {
      setError(null);
      const sessionId = await apiCreateSession();
      // Reload sessions to include the new one
      await loadSessions();
      return sessionId;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session');
      throw err;
    }
  };

  const deleteSession = async (sessionId: string) => {
    try {
      setError(null);
      await apiDeleteSession(sessionId);
      // Remove from local state
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete session');
      throw err;
    }
  };

  return {
    sessions,
    loading,
    error,
    createSession,
    deleteSession,
    refreshSessions: loadSessions,
  };
}
