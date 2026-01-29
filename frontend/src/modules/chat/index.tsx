/**
 * ChatModule - Main entry point for the chat module
 *
 * Contains ChatSidebar and ChatView with URL-based session management
 */

import React, { useState, useCallback } from 'react';
import { useParams, Outlet, useOutletContext } from 'react-router-dom';
import { ChatSidebar } from './ChatSidebar';
import { useSessions } from './hooks/useSessions';
import type { Session } from '../../types/message';

// Context type for child routes
interface ChatContextType {
  sessions: Session[];
  sessionTitle?: string;
  onAssistantRefresh: () => void;
}

export const ChatModule: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { sessions, createSession, deleteSession } = useSessions();
  const [, setAssistantRefreshKey] = useState(0);

  const handleAssistantRefresh = useCallback(() => {
    setAssistantRefreshKey((prev) => prev + 1);
  }, []);

  // Find current session title
  const currentSession = sessions.find((s) => s.session_id === sessionId);
  const sessionTitle = currentSession?.title;

  // Context to pass to child routes
  const context: ChatContextType = {
    sessions,
    sessionTitle,
    onAssistantRefresh: handleAssistantRefresh,
  };

  return (
    <div className="flex flex-1">
      {/* Chat Sidebar (Level 2) */}
      <ChatSidebar
        sessions={sessions}
        currentSessionId={sessionId || null}
        onNewSession={createSession}
        onDeleteSession={deleteSession}
      />

      {/* Chat Content */}
      <Outlet context={context} />
    </div>
  );
};

// Hook for child components to access chat context
export function useChatContext() {
  return useOutletContext<ChatContextType>();
}
