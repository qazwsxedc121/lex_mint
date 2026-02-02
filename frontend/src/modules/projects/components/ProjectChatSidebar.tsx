/**
 * ProjectChatSidebar - Chat sidebar for project-specific conversations
 * Manages project sessions and provides ChatView with project context
 */

import React, { useState, useEffect, useCallback } from 'react';
import { ChatView, useChatServices } from '../../../shared/chat';
import type { Message } from '../../../types/message';
import SessionSelector from './SessionSelector';
import { InsertToEditorButton } from './InsertToEditorButton';

interface ProjectChatSidebarProps {
  projectId: string;  // Current project ID
  currentSessionId: string | null;
  savedSessionId: string | null;
  onSetCurrentSessionId: (sessionId: string | null) => void;
}

export default function ProjectChatSidebar({
  projectId,
  currentSessionId,
  savedSessionId,
  onSetCurrentSessionId,
}: ProjectChatSidebarProps) {
  // Handle session selection
  const handleSelectSession = (sessionId: string) => {
    onSetCurrentSessionId(sessionId);
  };

  return (
    <div data-name="project-chat-sidebar-root" className="flex flex-col flex-1 min-h-0">
      <ChatServiceConsumer
        projectId={projectId}
        currentSessionId={currentSessionId}
        savedSessionId={savedSessionId}
        onSelectSession={handleSelectSession}
        onSetCurrentSessionId={onSetCurrentSessionId}
      />
    </div>
  );
}

/**
 * Inner component that consumes ChatServiceProvider context
 */
interface ChatServiceConsumerProps {
  projectId: string;
  currentSessionId: string | null;
  savedSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onSetCurrentSessionId: (sessionId: string | null) => void;
}

function ChatServiceConsumer({
  projectId,
  currentSessionId,
  savedSessionId,
  onSelectSession,
  onSetCurrentSessionId,
}: ChatServiceConsumerProps) {
  const { sessions, createSession, deleteSession, sessionsLoading } = useChatServices();
  const [initialized, setInitialized] = useState(false);
  const [sessionsLoaded, setSessionsLoaded] = useState(false);

  // Track when sessions have been loaded at least once
  useEffect(() => {
    if (!sessionsLoading && !sessionsLoaded) {
      setSessionsLoaded(true);
    }
  }, [sessionsLoading, sessionsLoaded]);

  // Reset initialization when project changes
  useEffect(() => {
    setInitialized(false);
    setSessionsLoaded(false);
  }, [projectId]);

  // Initialize: Restore saved session or auto-select first session
  useEffect(() => {
    // Wait for sessions to be loaded at least once
    if (!sessionsLoaded) {
      return;
    }

    // Only run initialization once when sessions are loaded
    if (initialized) {
      return;
    }

    const initialize = async () => {
      // Try to restore saved session first
      if (savedSessionId && sessions.some((s) => s.session_id === savedSessionId)) {
        onSetCurrentSessionId(savedSessionId);
      } else if (sessions.length > 0) {
        // Saved session not found or not set, select the most recent one
        onSetCurrentSessionId(sessions[0].session_id);
      }
      // Don't auto-create session - let user click "New Chat" button
      setInitialized(true);
    };

    initialize();
  }, [sessionsLoaded, initialized, sessions, savedSessionId, onSetCurrentSessionId]);

  // Handle session creation
  const handleCreateSession = async () => {
    try {
      const newSessionId = await createSession();
      onSetCurrentSessionId(newSessionId);
    } catch (error) {
      console.error('Failed to create session:', error);
      alert('Failed to create new conversation. Please try again.');
    }
  };

  // Handle session deletion
  const handleDeleteSession = async (sessionId: string) => {
    try {
      // If deleting current session, switch to another one first
      if (sessionId === currentSessionId) {
        const others = sessions.filter((s) => s.session_id !== sessionId);

        if (others.length > 0) {
          // Switch to the first remaining session
          onSetCurrentSessionId(others[0].session_id);
        } else {
          // No other sessions, clear current session (don't auto-create)
          await deleteSession(sessionId);
          onSetCurrentSessionId(null);
          return;
        }
      }

      // Delete the session
      await deleteSession(sessionId);
    } catch (error) {
      console.error('Failed to delete session:', error);
      alert('Failed to delete conversation. Please try again.');
    }
  };

  // Custom message actions for ChatView
  const customMessageActions = useCallback((message: Message, messageId: string) => (
    <InsertToEditorButton content={message.content} messageRole={message.role} />
  ), []);

  if (sessionsLoading && sessions.length === 0) {
    return (
      <div data-name="chat-loading" className="flex items-center justify-center h-full">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  return (
    <div data-name="chat-service-consumer" className="flex flex-col flex-1 min-h-0">
      {/* Session Selector */}
      <div data-name="session-selector-panel" className="border-b border-gray-300 dark:border-gray-700 p-3 bg-white dark:bg-gray-800">
        <SessionSelector
          sessions={sessions}
          currentSessionId={currentSessionId}
          onSelectSession={onSelectSession}
          onCreateSession={handleCreateSession}
          onDeleteSession={handleDeleteSession}
        />
      </div>

      {/* Chat View */}
      <div data-name="chat-view-container" className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <ChatView
          showHeader={false}
          customMessageActions={customMessageActions}
        />
      </div>
    </div>
  );
}
