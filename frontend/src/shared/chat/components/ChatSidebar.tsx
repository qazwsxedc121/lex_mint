/**
 * ChatSidebar - Session list sidebar (Level 2)
 *
 * Version 2.0: Self-contained, no external props needed
 * All data and operations from useChatServices
 * Version 2.1: Added folder organization support
 * Version 2.2: Added drag & drop support
 */

import React, { useState, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PlusIcon,
  MagnifyingGlassIcon,
  ArrowUpTrayIcon,
  FolderIcon,
  FolderOpenIcon,
  EllipsisHorizontalIcon,
} from '@heroicons/react/24/outline';
import {
  DndContext,
  DragOverlay,
  pointerWithin,
  type DragEndEvent,
  type DragStartEvent,
  type DragOverEvent,
} from '@dnd-kit/core';
import { useTranslation } from 'react-i18next';
import { useChatServices } from '../services/ChatServiceProvider';
import { useFolders } from '../hooks/useFolders';
import { exportSession, importChatGPTConversations, importMarkdownConversation, listProjects } from '../../../services/api';
import type { Session } from '../../../types/message';
import type { Project } from '../../../types/project';
import { SessionTransferModal } from './SessionTransferModal';
import { FolderModal } from './FolderModal';
import { DraggableSession } from './DraggableSession';
import { DroppableFolderHeader } from './DroppableFolderHeader';

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
    today: [],
    yesterday: [],
    thisWeek: [],
    thisMonth: [],
    older: [],
  };

  for (const session of sessions) {
    const raw = session.updated_at || session.created_at;
    const date = raw ? new Date(raw.replace(' ', 'T')) : new Date(0);

    if (date >= today) {
      groups['today'].push(session);
    } else if (date >= yesterday) {
      groups['yesterday'].push(session);
    } else if (date >= weekAgo) {
      groups['thisWeek'].push(session);
    } else if (date >= monthAgo) {
      groups['thisMonth'].push(session);
    } else {
      groups['older'].push(session);
    }
  }

  const orderedLabels = ['today', 'yesterday', 'thisWeek', 'thisMonth', 'older'];
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

  const { t } = useTranslation('chat');
  const {
    folders,
    collapsedFolders,
    createFolder: apiCreateFolder,
    updateFolder: apiUpdateFolder,
    deleteFolder: apiDeleteFolder,
    moveSessionToFolder,
    reorderFolder,
    toggleFolder,
  } = useFolders();

  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [generatingTitleId, setGeneratingTitleId] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const [showTimeGroups, setShowTimeGroups] = useState(() => {
    return localStorage.getItem('chat-show-time-groups') === 'true';
  });
  const [transferState, setTransferState] = useState<{ sessionId: string; mode: 'move' | 'copy' } | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [transferBusy, setTransferBusy] = useState(false);

  // Drag & drop state
  const [draggedItem, setDraggedItem] = useState<{
    id: string;
    type: 'session' | 'folder';
    data: any;
  } | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);

  // Folder UI states
  const [folderModalState, setFolderModalState] = useState<{
    open: boolean;
    mode: 'create' | 'edit';
    folderId?: string;
    initialName?: string;
  }>({ open: false, mode: 'create' });

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
      alert(t('sidebar.importAlertJson'));
      if (chatgptInputRef.current) {
        chatgptInputRef.current.value = '';
      }
      return;
    }

    setImporting(true);
    try {
      const result = await importChatGPTConversations(file);
      await refreshSessions();

      const errorCount = result.errors?.length || 0;
      const message = t('sidebar.importResult', { imported: result.imported, skipped: result.skipped }) +
        (errorCount ? t('sidebar.importErrors', { count: errorCount }) : '');
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
      alert(t('sidebar.importAlertMd'));
      if (markdownInputRef.current) {
        markdownInputRef.current.value = '';
      }
      return;
    }

    setImporting(true);
    try {
      const result = await importMarkdownConversation(file);
      await refreshSessions();

      const errorCount = result.errors?.length || 0;
      const message = t('sidebar.importResult', { imported: result.imported, skipped: result.skipped }) +
        (errorCount ? t('sidebar.importErrors', { count: errorCount }) : '');
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
    if (confirm(t('sidebar.deleteConfirm'))) {
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
      alert(t('sidebar.failedGenerateTitle'));
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
      alert(t('sidebar.failedUpdateTitle'));
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
      alert(t('sidebar.failedDuplicate'));
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
      alert(t('sidebar.failedTransfer'));
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
      alert(t('sidebar.failedExport'));
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

  // Close "More" menu when clicking outside
  React.useEffect(() => {
    const handleClickOutside = () => setMoreMenuOpen(false);
    if (moreMenuOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [moreMenuOpen]);

  // Persist time groups preference
  React.useEffect(() => {
    localStorage.setItem('chat-show-time-groups', showTimeGroups.toString());
  }, [showTimeGroups]);

  // Group sessions by folder
  const { folderGroups, ungroupedSessions } = useMemo(() => {
    const grouped: Record<string, Session[]> = {};
    const ungrouped: Session[] = [];

    sessions.forEach((session) => {
      if (session.folder_id) {
        if (!grouped[session.folder_id]) {
          grouped[session.folder_id] = [];
        }
        grouped[session.folder_id].push(session);
      } else {
        ungrouped.push(session);
      }
    });

    return { folderGroups: grouped, ungroupedSessions: ungrouped };
  }, [sessions]);

  // Time-based grouping for ungrouped sessions
  const groupedUngrouped = useMemo(() => groupSessionsByTime(ungroupedSessions), [ungroupedSessions]);

  // Folder CRUD handlers
  const handleCreateFolder = async (name: string): Promise<boolean> => {
    const folder = await apiCreateFolder(name);
    return folder !== null;
  };

  const handleRenameFolder = async (name: string): Promise<boolean> => {
    if (!folderModalState.folderId) return false;
    return await apiUpdateFolder(folderModalState.folderId, name);
  };

  const handleDeleteFolder = async (folderId: string) => {
    if (!confirm(t('sidebar.deleteFolderConfirm'))) return;
    const success = await apiDeleteFolder(folderId);
    if (success) {
      await refreshSessions();
    }
  };

  const handleMoveToFolder = async (sessionId: string, folderId: string | null) => {
    const success = await moveSessionToFolder(sessionId, folderId);
    if (success) {
      await refreshSessions();
    }
    setOpenMenuId(null);
  };

  // Drag & drop handlers
  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    setDraggedItem({
      id: active.id as string,
      type: active.data.current?.type,
      data: active.data.current
    });
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { over } = event;
    setDropTargetId(over ? (over.id as string) : null);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setDraggedItem(null);
    setDropTargetId(null);

    if (!over || active.id === over.id) return;

    const dragData = active.data.current;
    const dropData = over.data.current;

    // Session dropped on folder header
    if (dragData?.type === 'session' && dropData?.type === 'folder-drop') {
      const success = await moveSessionToFolder(dragData.sessionId, dropData.folderId);
      if (success) {
        await refreshSessions();
      }
      return;
    }

    // Folder reordering: folder dragged to another folder
    if (dragData?.type === 'folder' && dropData?.type === 'folder-drop' && dropData?.acceptsFolder) {
      const oldIndex = folders.findIndex(f => f.id === dragData.folderId);
      const newIndex = folders.findIndex(f => f.id === dropData.folderId);

      if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
        await reorderFolder(dragData.folderId, newIndex);
      }
      return;
    }

    // Legacy: folder to folder (in case the above doesn't match)
    if (dragData?.type === 'folder' && dropData?.type === 'folder') {
      const oldIndex = folders.findIndex(f => f.id === dragData.folderId);
      const newIndex = folders.findIndex(f => f.id === dropData.folderId);

      if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
        await reorderFolder(dragData.folderId, newIndex);
      }
    }
  };

  const renderDragOverlay = () => {
    if (!draggedItem) return null;

    if (draggedItem.type === 'session') {
      const session = sessions.find(s => s.session_id === draggedItem.id);
      return (
        <div className="bg-white dark:bg-gray-800 p-3 rounded shadow-lg border border-gray-300 dark:border-gray-600 max-w-xs">
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
            {session?.title || 'Session'}
          </p>
        </div>
      );
    }

    if (draggedItem.type === 'folder') {
      const folder = folders.find(f => f.id === draggedItem.data.folderId);
      return (
        <div className="bg-gray-50 dark:bg-gray-800 p-2 rounded shadow-lg border border-gray-300 dark:border-gray-600 flex items-center gap-2">
          <FolderIcon className="h-4 w-4 text-amber-500" />
          <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">{folder?.name}</span>
        </div>
      );
    }

    return null;
  };

  return (
    <div data-name="chat-sidebar" className="w-64 bg-gray-100 dark:bg-gray-800 border-r border-gray-300 dark:border-gray-700 flex flex-col">
      {/* Toolbar */}
      <div data-name="chat-sidebar-toolbar" className="flex items-center gap-1 px-3 py-2 border-b border-gray-300 dark:border-gray-700">
        <button
          onClick={handleNewSession}
          className="p-2 rounded-lg text-blue-500 dark:text-blue-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          title={t('sidebar.newChat')}
        >
          <PlusIcon className="h-5 w-5" />
        </button>
        <button
          onClick={handleNewTemporarySession}
          className="p-2 rounded-lg text-gray-400 dark:text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          title={t('sidebar.tempChat')}
        >
          <PlusIcon className="h-5 w-5" />
        </button>

        {/* "More" dropdown menu */}
        <div data-name="chat-sidebar-more-menu" className="relative">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setMoreMenuOpen(!moreMenuOpen);
            }}
            className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
            title={t('sidebar.moreOptions')}
          >
            <EllipsisHorizontalIcon className="h-5 w-5" />
          </button>

          {moreMenuOpen && (
            <div className="absolute left-0 mt-1 w-56 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md shadow-lg z-10">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  chatgptInputRef.current?.click();
                  setMoreMenuOpen(false);
                }}
                disabled={importing}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2 disabled:opacity-60"
              >
                <ArrowUpTrayIcon className="h-4 w-4 text-emerald-500" />
                {t('sidebar.importChatGPT')}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  markdownInputRef.current?.click();
                  setMoreMenuOpen(false);
                }}
                disabled={importing}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2 disabled:opacity-60"
              >
                <ArrowUpTrayIcon className="h-4 w-4 text-emerald-500" />
                {t('sidebar.importMarkdown')}
              </button>

              <div className="border-t border-gray-200 dark:border-gray-600 my-1" />

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setFolderModalState({ open: true, mode: 'create' });
                  setMoreMenuOpen(false);
                }}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
              >
                <FolderIcon className="h-4 w-4 text-amber-500" />
                {t('sidebar.newFolder')}
              </button>

              <div className="border-t border-gray-200 dark:border-gray-600 my-1" />

              <label
                className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2 cursor-pointer"
                onClick={(e) => e.stopPropagation()}
              >
                <input
                  type="checkbox"
                  checked={showTimeGroups}
                  onChange={(e) => setShowTimeGroups(e.target.checked)}
                  className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                {t('sidebar.showTimeGroups')}
              </label>
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
          title={t('sidebar.searchCtrlK')}
        >
          <MagnifyingGlassIcon className="h-5 w-5" />
        </button>
      </div>

      {/* Session List */}
      <div data-name="chat-sidebar-sessions" className="flex-1 overflow-y-auto">
        <DndContext
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
          collisionDetection={pointerWithin}
        >
          {sessions.length === 0 ? (
            <div className="p-4 text-center text-gray-500 dark:text-gray-400">
              {t('sidebar.noConversations')}
            </div>
          ) : (
            <>
              {/* Render Folders */}
              {folders.map((folder, folderIndex) => {
                const folderSessions = folderGroups[folder.id] || [];
                const isCollapsed = collapsedFolders.has(folder.id);
                const isDropTarget = dropTargetId === `folder-drop-${folder.id}`;

                return (
                  <div key={`folder-${folder.id}-${folderIndex}`}>
                    <DroppableFolderHeader
                      folder={folder}
                      sessionCount={folderSessions.length}
                      isCollapsed={isCollapsed}
                      isDropTarget={isDropTarget}
                      onToggle={() => toggleFolder(folder.id)}
                      onRename={() => setFolderModalState({ open: true, mode: 'edit', folderId: folder.id, initialName: folder.name })}
                      onDelete={() => handleDeleteFolder(folder.id)}
                    />

                    {/* Folder Sessions */}
                    {!isCollapsed && folderSessions.map((session, sessionIndex) => (
                      <DraggableSession
                        key={`folder-session-${session.session_id}-${sessionIndex}`}
                        session={session}
                        currentSessionId={currentSessionId}
                        editingSessionId={editingSessionId}
                        editTitle={editTitle}
                        generatingTitleId={generatingTitleId}
                        openMenuId={openMenuId}
                        folders={folders}
                        onSelect={handleSelectSession}
                        onDelete={handleDeleteSession}
                        onMenuClick={handleMenuClick}
                        onGenerateTitle={handleGenerateTitle}
                        onStartEdit={handleStartEdit}
                        onSaveEdit={handleSaveEdit}
                        onCancelEdit={handleCancelEdit}
                        onDuplicate={handleDuplicate}
                        onOpenTransfer={handleOpenTransfer}
                        onExport={handleExport}
                        onMoveToFolder={handleMoveToFolder}
                        setEditTitle={setEditTitle}
                      />
                    ))}
                  </div>
                );
              })}

              {/* Ungrouped Sessions */}
              {ungroupedSessions.length > 0 && (
                <div>
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-800/80 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
                      <FolderOpenIcon className="h-4 w-4 text-gray-500" />
                      <span>{t('sidebar.ungrouped')}</span>
                      <span className="text-xs text-gray-500">({ungroupedSessions.length})</span>
                    </div>
                  </div>

                  {showTimeGroups ? (
                    groupedUngrouped.map((group) => (
                      <div key={group.label}>
                        <div className="px-3 py-1.5 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider bg-gray-50 dark:bg-gray-800/80 sticky top-0 z-[1]">
                          {t('timeGroup.' + group.label)}
                        </div>
                        {group.sessions.map((session, sessionIndex) => (
                          <DraggableSession
                            key={`ungrouped-session-${session.session_id}-${sessionIndex}`}
                            session={session}
                            currentSessionId={currentSessionId}
                            editingSessionId={editingSessionId}
                            editTitle={editTitle}
                            generatingTitleId={generatingTitleId}
                            openMenuId={openMenuId}
                            folders={folders}
                            onSelect={handleSelectSession}
                            onDelete={handleDeleteSession}
                            onMenuClick={handleMenuClick}
                            onGenerateTitle={handleGenerateTitle}
                            onStartEdit={handleStartEdit}
                            onSaveEdit={handleSaveEdit}
                            onCancelEdit={handleCancelEdit}
                            onDuplicate={handleDuplicate}
                            onOpenTransfer={handleOpenTransfer}
                            onExport={handleExport}
                            onMoveToFolder={handleMoveToFolder}
                            setEditTitle={setEditTitle}
                          />
                        ))}
                      </div>
                    ))
                  ) : (
                    ungroupedSessions.map((session, sessionIndex) => (
                      <DraggableSession
                        key={`ungrouped-session-${session.session_id}-${sessionIndex}`}
                        session={session}
                        currentSessionId={currentSessionId}
                        editingSessionId={editingSessionId}
                        editTitle={editTitle}
                        generatingTitleId={generatingTitleId}
                        openMenuId={openMenuId}
                        folders={folders}
                        onSelect={handleSelectSession}
                        onDelete={handleDeleteSession}
                        onMenuClick={handleMenuClick}
                        onGenerateTitle={handleGenerateTitle}
                        onStartEdit={handleStartEdit}
                        onSaveEdit={handleSaveEdit}
                        onCancelEdit={handleCancelEdit}
                        onDuplicate={handleDuplicate}
                        onOpenTransfer={handleOpenTransfer}
                        onExport={handleExport}
                        onMoveToFolder={handleMoveToFolder}
                        setEditTitle={setEditTitle}
                      />
                    ))
                  )}
                </div>
              )}
            </>
          )}

          <DragOverlay>
            {renderDragOverlay()}
          </DragOverlay>
        </DndContext>
      </div>

      <FolderModal
        isOpen={folderModalState.open}
        mode={folderModalState.mode}
        initialName={folderModalState.initialName}
        onConfirm={folderModalState.mode === 'create' ? handleCreateFolder : handleRenameFolder}
        onClose={() => setFolderModalState({ open: false, mode: 'create' })}
      />

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
