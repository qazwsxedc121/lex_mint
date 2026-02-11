/**
 * ChatSidebar - Session list sidebar (Level 2)
 *
 * Version 2.0: Self-contained, no external props needed
 * All data and operations from useChatServices
 */

import React, { useState, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  EllipsisVerticalIcon,
  TrashIcon,
  PencilIcon,
  DocumentDuplicateIcon,
  SparklesIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  ChatBubbleLeftRightIcon,
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  ArrowRightOnRectangleIcon,
} from '@heroicons/react/24/outline';
import { useChatServices } from '../services/ChatServiceProvider';
import { exportSession, importChatGPTConversations, importMarkdownConversation, listProjects } from '../../../services/api';
import type { Session } from '../../../types/message';
import type { Project } from '../../../types/project';
import { SessionTransferModal } from './SessionTransferModal';

/**
 * Group sessions by time period based on updated_at (or created_at fallback).
 * Returns an ordered array of { label, sessions } groups.
 */
function groupSessionsByTime(sessions: Session[]): { label: string; sessions: Session[] }[] {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const weekAgo = new Date(today);
  weekAgo.setDate(weekAgo.getDate() - 7);
  const monthAgo = new Date(today);
  monthAgo.setMonth(monthAgo.getMonth() - 1);

  const groups: Record<string, Session[]> = {
    Today: [],
    Yesterday: [],
    'This Week': [],
    'This Month': [],
    Older: [],
  };

  for (const session of sessions) {
    const raw = session.updated_at || session.created_at;
    const date = raw ? new Date(raw.replace(' ', 'T')) : new Date(0);

    if (date >= today) {
      groups['Today'].push(session);
    } else if (date >= yesterday) {
      groups['Yesterday'].push(session);
    } else if (date >= weekAgo) {
      groups['This Week'].push(session);
    } else if (date >= monthAgo) {
      groups['This Month'].push(session);
    } else {
      groups['Older'].push(session);
    }
  }

  const orderedLabels = ['Today', 'Yesterday', 'This Week', 'This Month', 'Older'];
  return orderedLabels
    .filter((label) => groups[label].length > 0)
    .map((label) => ({ label, sessions: groups[label] }));
}

export const ChatSidebar: React.FC = () => {
  const navigate = useNavigate();
  const {
    api,
    navigation,
    sessions,
    currentSessionId,
    createSession,
    createTemporarySession,
    deleteSession,
    refreshSessions,
  } = useChatServices();

  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [generatingTitleId, setGeneratingTitleId] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importMenuOpen, setImportMenuOpen] = useState(false);
  const [transferState, setTransferState] = useState<{ sessionId: string; mode: 'move' | 'copy' } | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [transferBusy, setTransferBusy] = useState(false);
  const chatgptInputRef = useRef<HTMLInputElement>(null);
  const markdownInputRef = useRef<HTMLInputElement>(null);

  const loadProjects = React.useCallback(async () => {
    try {
      setProjectsLoading(true);
      setProjectsError(null);
      const data = await listProjects();
      setProjects(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load projects';
      setProjectsError(message);
    } finally {
      setProjectsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (transferState) {
      loadProjects();
    }
  }, [transferState, loadProjects]);

  const handleNewSession = async () => {
    try {
      const sessionId = await createSession();
      if (navigation) {
        navigation.navigateToSession(sessionId);
      } else {
        navigate(`/chat/${sessionId}`);
      }
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  const handleNewTemporarySession = async () => {
    try {
      const sessionId = await createTemporarySession();
      if (navigation) {
        navigation.navigateToSession(sessionId);
      } else {
        navigate(`/chat/${sessionId}`);
      }
    } catch (err) {
      console.error('Failed to create temporary session:', err);
    }
  };

  const handleImportChatGPT = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const [file] = Array.from(files);
    if (!file) return;

    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith('.json') && !lowerName.endsWith('.zip')) {
      alert('Please select a ChatGPT .json or .zip export file.');
      if (chatgptInputRef.current) {
        chatgptInputRef.current.value = '';
      }
      return;
    }

    setImporting(true);
    setImportMenuOpen(false);
    try {
      const result = await importChatGPTConversations(file);
      await refreshSessions();

      const errorCount = result.errors?.length || 0;
      const message = `Imported ${result.imported} conversation(s). Skipped ${result.skipped}.` +
        (errorCount ? ` Errors: ${errorCount}.` : '');
      alert(message);

      if (errorCount) {
        console.error('ChatGPT import errors:', result.errors);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to import ChatGPT conversations';
      console.error('Failed to import ChatGPT conversations:', err);
      alert(message);
    } finally {
      setImporting(false);
      if (chatgptInputRef.current) {
        chatgptInputRef.current.value = '';
      }
    }
  };

  const handleImportMarkdown = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const [file] = Array.from(files);
    if (!file) return;

    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith('.md') && !lowerName.endsWith('.markdown')) {
      alert('Please select a Markdown (.md) conversation file.');
      if (markdownInputRef.current) {
        markdownInputRef.current.value = '';
      }
      return;
    }

    setImporting(true);
    setImportMenuOpen(false);
    try {
      const result = await importMarkdownConversation(file);
      await refreshSessions();

      const errorCount = result.errors?.length || 0;
      const message = `Imported ${result.imported} conversation(s). Skipped ${result.skipped}.` +
        (errorCount ? ` Errors: ${errorCount}.` : '');
      alert(message);

      if (errorCount) {
        console.error('Markdown import errors:', result.errors);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to import Markdown conversation';
      console.error('Failed to import Markdown conversation:', err);
      alert(message);
    } finally {
      setImporting(false);
      if (markdownInputRef.current) {
        markdownInputRef.current.value = '';
      }
    }
  };

  const handleSelectSession = (sessionId: string) => {
    if (navigation) {
      navigation.navigateToSession(sessionId);
    } else {
      navigate(`/chat/${sessionId}`);
    }
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this conversation?')) {
      try {
        await deleteSession(sessionId);
        // If deleted session was active, navigate to chat root
        if (currentSessionId === sessionId) {
          if (navigation) {
            navigation.navigateToRoot();
          } else {
            navigate('/chat');
          }
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
      await api.generateTitleManually(sessionId);
      await refreshSessions();
    } catch (err) {
      console.error('Failed to generate title:', err);
      alert('Failed to generate title');
    } finally {
      setGeneratingTitleId(null);
    }
  };

  const handleStartEdit = (e: React.MouseEvent, sessionId: string, currentTitle: string) => {
    e.stopPropagation();
    setOpenMenuId(null);
    setEditingSessionId(sessionId);
    setEditTitle(currentTitle);
  };

  const handleSaveEdit = async (sessionId: string) => {
    if (!editTitle.trim()) return;

    try {
      await api.updateSessionTitle(sessionId, editTitle.trim());
      setEditingSessionId(null);
      await refreshSessions();
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
      const newSessionId = await api.duplicateSession(sessionId);
      await refreshSessions();
      if (navigation) {
        navigation.navigateToSession(newSessionId);
      } else {
        navigate(`/chat/${newSessionId}`);
      }
    } catch (err) {
      console.error('Failed to duplicate session:', err);
      alert('Failed to duplicate session');
    }
  };

  const handleOpenTransfer = (e: React.MouseEvent, sessionId: string, mode: 'move' | 'copy') => {
    e.stopPropagation();
    setOpenMenuId(null);
    setTransferState({ sessionId, mode });
  };

  const handleSelectTransferTarget = async (targetContextType: 'chat' | 'project', targetProjectId?: string) => {
    if (!transferState) return;

    try {
      setTransferBusy(true);
      if (transferState.mode === 'move') {
        await api.moveSession(transferState.sessionId, targetContextType, targetProjectId);
        await refreshSessions();
        if (currentSessionId === transferState.sessionId && targetContextType !== 'chat') {
          if (navigation) {
            navigation.navigateToRoot();
          } else {
            navigate('/chat');
          }
        }
      } else {
        await api.copySession(transferState.sessionId, targetContextType, targetProjectId);
        await refreshSessions();
      }
    } catch (err) {
      console.error('Failed to transfer session:', err);
      alert('Failed to transfer conversation');
    } finally {
      setTransferBusy(false);
      setTransferState(null);
    }
  };

  const handleExport = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setOpenMenuId(null);

    try {
      await exportSession(sessionId);
    } catch (err) {
      console.error('Failed to export session:', err);
      alert('Failed to export session');
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

  // Close import menu when clicking outside
  React.useEffect(() => {
    const handleClickOutside = () => setImportMenuOpen(false);
    if (importMenuOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [importMenuOpen]);

  const groupedSessions = useMemo(() => groupSessionsByTime(sessions), [sessions]);

  return (
    <div data-name="chat-sidebar" className="w-64 bg-gray-100 dark:bg-gray-800 border-r border-gray-300 dark:border-gray-700 flex flex-col">
      {/* Toolbar */}
      <div data-name="chat-sidebar-toolbar" className="flex items-center gap-1 px-3 py-2 border-b border-gray-300 dark:border-gray-700">
        <button
          onClick={handleNewSession}
          className="p-2 rounded-lg text-blue-500 dark:text-blue-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          title="New Chat"
        >
          <PlusIcon className="h-5 w-5" />
        </button>
        <button
          onClick={handleNewTemporarySession}
          className="p-2 rounded-lg text-gray-400 dark:text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          title="Temp Chat"
        >
          <PlusIcon className="h-5 w-5" />
        </button>
        <div data-name="chat-sidebar-import" className="relative">
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (!importing) {
                setImportMenuOpen(!importMenuOpen);
              }
            }}
            disabled={importing}
            className="p-2 rounded-lg text-emerald-500 dark:text-emerald-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-60"
            title={importing ? 'Importing...' : 'Import conversations'}
          >
            <ArrowUpTrayIcon className="h-5 w-5" />
          </button>
          {importMenuOpen && (
            <div className="absolute left-0 mt-1 w-56 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md shadow-lg z-10">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  chatgptInputRef.current?.click();
                }}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600"
              >
                Import ChatGPT (.json/.zip)
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  markdownInputRef.current?.click();
                }}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600"
              >
                Import Markdown (.md)
              </button>
            </div>
          )}
          <input
            ref={chatgptInputRef}
            type="file"
            accept=".json,.zip,application/json,application/zip"
            className="hidden"
            onChange={(e) => handleImportChatGPT(e.target.files)}
          />
          <input
            ref={markdownInputRef}
            type="file"
            accept=".md,.markdown,text/markdown"
            className="hidden"
            onChange={(e) => handleImportMarkdown(e.target.files)}
          />
        </div>
        <button
          onClick={() => window.dispatchEvent(new CustomEvent('open-command-palette'))}
          className="ml-auto p-2 rounded-lg text-gray-400 dark:text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          title="Search (Ctrl+K)"
        >
          <MagnifyingGlassIcon className="h-5 w-5" />
        </button>
      </div>

      {/* Session List */}
      <div data-name="chat-sidebar-sessions" className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">
            No conversations
          </div>
        ) : (
          groupedSessions.map((group) => (
            <div key={group.label}>
              <div className="px-3 py-1.5 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider bg-gray-50 dark:bg-gray-800/80 sticky top-0 z-[1]">
                {group.label}
              </div>
              {group.sessions.map((session) => (
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
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-1">
                        <ChatBubbleLeftRightIcon className="w-3 h-3" />
                        <span>{session.message_count || 0}</span>
                        {session.updated_at && (
                          <>
                            <span className="mx-0.5">-</span>
                            <span>{session.updated_at}</span>
                          </>
                        )}
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
                          onClick={(e) => handleStartEdit(e, session.session_id, session.title)}
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
                        <button
                          onClick={(e) => handleOpenTransfer(e, session.session_id, 'move')}
                          className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                        >
                          <ArrowRightOnRectangleIcon className="h-4 w-4" />
                          Move to Project
                        </button>
                        <button
                          onClick={(e) => handleOpenTransfer(e, session.session_id, 'copy')}
                          className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                        >
                          <DocumentDuplicateIcon className="h-4 w-4" />
                          Copy to Project
                        </button>
                        <button
                          onClick={(e) => handleExport(e, session.session_id)}
                          className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                        >
                          <ArrowDownTrayIcon className="h-4 w-4" />
                          Export
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
          ))}
            </div>
          ))
        )}
      </div>

      <SessionTransferModal
        isOpen={Boolean(transferState)}
        mode={transferState?.mode || 'move'}
        projects={projects}
        loading={projectsLoading}
        error={projectsError}
        busy={transferBusy}
        showChatOption={false}
        onClose={() => setTransferState(null)}
        onSelectTarget={handleSelectTransferTarget}
        onRetry={loadProjects}
      />
    </div>
  );
};
