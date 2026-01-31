/**
 * ChatSidebar - Session list sidebar (Level 2)
 *
 * Displays session list with create/delete functionality
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  EllipsisVerticalIcon,
  TrashIcon,
  PencilIcon,
  DocumentDuplicateIcon,
  SparklesIcon
} from '@heroicons/react/24/outline';
import type { Session } from '../../types/message';
import { generateTitleManually, updateSessionTitle, duplicateSession } from '../../services/api';

interface ChatSidebarProps {
  sessions: Session[];
  currentSessionId: string | null;
  onNewSession: () => Promise<string>;
  onDeleteSession: (sessionId: string) => Promise<void>;
  onRefresh?: () => void;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  sessions,
  currentSessionId,
  onNewSession,
  onDeleteSession,
  onRefresh,
}) => {
  const navigate = useNavigate();
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [generatingTitleId, setGeneratingTitleId] = useState<string | null>(null);

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

  const handleMenuClick = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setOpenMenuId(openMenuId === sessionId ? null : sessionId);
  };

  const handleGenerateTitle = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setOpenMenuId(null);

    try {
      setGeneratingTitleId(sessionId);
      await generateTitleManually(sessionId);
      onRefresh?.();
    } catch (err) {
      console.error('Failed to generate title:', err);
      alert('Failed to generate title');
    } finally {
      setGeneratingTitleId(null);
    }
  };

  const handleStartEdit = (e: React.MouseEvent, session: Session) => {
    e.stopPropagation();
    setOpenMenuId(null);
    setEditingSessionId(session.session_id);
    setEditTitle(session.title);
  };

  const handleSaveEdit = async (sessionId: string) => {
    if (!editTitle.trim()) return;

    try {
      await updateSessionTitle(sessionId, editTitle.trim());
      setEditingSessionId(null);
      onRefresh?.();
    } catch (err) {
      console.error('Failed to update title:', err);
      alert('Failed to update title');
    }
  };

  const handleCancelEdit = () => {
    setEditingSessionId(null);
    setEditTitle('');
  };

  const handleDuplicate = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setOpenMenuId(null);

    try {
      const newSessionId = await duplicateSession(sessionId);
      onRefresh?.();
      navigate(`/chat/${newSessionId}`);
    } catch (err) {
      console.error('Failed to duplicate session:', err);
      alert('Failed to duplicate session');
    }
  };

  // Close menu when clicking outside
  React.useEffect(() => {
    const handleClickOutside = () => setOpenMenuId(null);
    if (openMenuId) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [openMenuId]);

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
                <div className="flex-1 min-w-0 pr-2">
                  {editingSessionId === session.session_id ? (
                    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveEdit(session.session_id);
                          if (e.key === 'Escape') handleCancelEdit();
                        }}
                        className="flex-1 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                        autoFocus
                      />
                      <button
                        onClick={() => handleSaveEdit(session.session_id)}
                        className="text-green-600 hover:text-green-700 dark:text-green-400 dark:hover:text-green-300 text-xs px-1"
                      >
                        OK
                      </button>
                      <button
                        onClick={handleCancelEdit}
                        className="text-gray-600 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 text-xs px-1"
                      >
                        X
                      </button>
                    </div>
                  ) : (
                    <>
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                        {generatingTitleId === session.session_id ? (
                          <span className="text-gray-500 dark:text-gray-400">Generating...</span>
                        ) : (
                          session.title
                        )}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {session.message_count || 0} messages
                      </p>
                    </>
                  )}
                </div>

                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {/* Menu Button */}
                  <div className="relative">
                    <button
                      onClick={(e) => handleMenuClick(e, session.session_id)}
                      className="p-1 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
                      title="More options"
                    >
                      <EllipsisVerticalIcon className="h-4 w-4" />
                    </button>

                    {/* Dropdown Menu */}
                    {openMenuId === session.session_id && (
                      <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md shadow-lg z-10">
                        <button
                          onClick={(e) => handleGenerateTitle(e, session.session_id)}
                          className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                        >
                          <SparklesIcon className="h-4 w-4" />
                          Generate Title
                        </button>
                        <button
                          onClick={(e) => handleStartEdit(e, session)}
                          className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                        >
                          <PencilIcon className="h-4 w-4" />
                          Rename
                        </button>
                        <button
                          onClick={(e) => handleDuplicate(e, session.session_id)}
                          className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                        >
                          <DocumentDuplicateIcon className="h-4 w-4" />
                          Duplicate
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Delete Button */}
                  <button
                    onClick={(e) => handleDeleteSession(session.session_id, e)}
                    className="p-1 text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                    title="Delete conversation"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
