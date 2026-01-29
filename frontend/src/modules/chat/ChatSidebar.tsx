/**
 * ChatSidebar - Session list sidebar (Level 2)
 *
 * Displays session list with create/delete functionality
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import type { Session } from '../../types/message';

interface ChatSidebarProps {
  sessions: Session[];
  currentSessionId: string | null;
  onNewSession: () => Promise<string>;
  onDeleteSession: (sessionId: string) => Promise<void>;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  sessions,
  currentSessionId,
  onNewSession,
  onDeleteSession,
}) => {
  const navigate = useNavigate();

  const handleNewSession = async () => {
    try {
      const sessionId = await onNewSession();
      navigate(`/chat/${sessionId}`);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  const handleSelectSession = (sessionId: string) => {
    navigate(`/chat/${sessionId}`);
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this conversation?')) {
      try {
        await onDeleteSession(sessionId);
        // If deleted session was active, navigate to chat root
        if (currentSessionId === sessionId) {
          navigate('/chat');
        }
      } catch (err) {
        console.error('Failed to delete session:', err);
      }
    }
  };

  return (
    <div className="w-64 bg-gray-100 dark:bg-gray-800 border-r border-gray-300 dark:border-gray-700 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-300 dark:border-gray-700">
        <button
          onClick={handleNewSession}
          className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
        >
          + New Chat
        </button>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">
            No conversations
          </div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.session_id}
              className={`group relative p-3 border-b border-gray-200 dark:border-gray-700 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors ${
                currentSessionId === session.session_id
                  ? 'bg-gray-200 dark:bg-gray-700'
                  : ''
              }`}
              onClick={() => handleSelectSession(session.session_id)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                    {session.title}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {session.message_count || 0} messages
                  </p>
                </div>
                <button
                  onClick={(e) => handleDeleteSession(session.session_id, e)}
                  className="opacity-0 group-hover:opacity-100 ml-2 p-1 text-red-500 hover:text-red-700 transition-opacity"
                  title="Delete conversation"
                >
                  ×
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
