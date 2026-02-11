/**
 * DraggableSession - Draggable session item component
 */

import React from 'react';
import {
  EllipsisVerticalIcon,
  TrashIcon,
  PencilIcon,
  DocumentDuplicateIcon,
  SparklesIcon,
  ChatBubbleLeftRightIcon,
  ArrowDownTrayIcon,
  ArrowRightOnRectangleIcon,
  FolderIcon,
} from '@heroicons/react/24/outline';
import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import type { Session } from '../../../types/message';
import type { Folder } from '../../../types/folder';

interface DraggableSessionProps {
  session: Session;
  currentSessionId: string | null;
  editingSessionId: string | null;
  editTitle: string;
  generatingTitleId: string | null;
  openMenuId: string | null;
  folders: Folder[];
  onSelect: (sessionId: string) => void;
  onDelete: (sessionId: string, e: React.MouseEvent) => void;
  onMenuClick: (e: React.MouseEvent, sessionId: string) => void;
  onGenerateTitle: (e: React.MouseEvent, sessionId: string) => void;
  onStartEdit: (e: React.MouseEvent, sessionId: string, currentTitle: string) => void;
  onSaveEdit: (sessionId: string) => void;
  onCancelEdit: () => void;
  onDuplicate: (e: React.MouseEvent, sessionId: string) => void;
  onOpenTransfer: (e: React.MouseEvent, sessionId: string, mode: 'move' | 'copy') => void;
  onExport: (e: React.MouseEvent, sessionId: string) => void;
  onMoveToFolder: (sessionId: string, folderId: string | null) => void;
  setEditTitle: (title: string) => void;
}

export const DraggableSession: React.FC<DraggableSessionProps> = ({
  session,
  currentSessionId,
  editingSessionId,
  editTitle,
  generatingTitleId,
  openMenuId,
  folders,
  onSelect,
  onDelete,
  onMenuClick,
  onGenerateTitle,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onDuplicate,
  onOpenTransfer,
  onExport,
  onMoveToFolder,
  setEditTitle,
}) => {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: session.session_id,
    data: {
      type: 'session',
      sessionId: session.session_id,
      folderId: session.folder_id
    },
    disabled: editingSessionId === session.session_id,
  });

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`group relative p-3 border-b border-gray-200 dark:border-gray-700 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors ${
        currentSessionId === session.session_id
          ? 'bg-gray-200 dark:bg-gray-700'
          : ''
      } ${isDragging ? 'opacity-50' : ''}`}
      onClick={() => onSelect(session.session_id)}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0 pr-2" {...attributes} {...listeners}>
          {editingSessionId === session.session_id ? (
            <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onSaveEdit(session.session_id);
                  if (e.key === 'Escape') onCancelEdit();
                }}
                className="flex-1 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                autoFocus
              />
              <button
                onClick={() => onSaveEdit(session.session_id)}
                className="text-green-600 hover:text-green-700 dark:text-green-400 dark:hover:text-green-300 text-xs px-1"
              >
                OK
              </button>
              <button
                onClick={onCancelEdit}
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

        <div
          className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="relative">
            <button
              onClick={(e) => onMenuClick(e, session.session_id)}
              className="p-1 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
              title="More options"
            >
              <EllipsisVerticalIcon className="h-4 w-4" />
            </button>

            {openMenuId === session.session_id && (
              <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md shadow-lg z-10">
                <button
                  onClick={(e) => onGenerateTitle(e, session.session_id)}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                >
                  <SparklesIcon className="h-4 w-4" />
                  Generate Title
                </button>
                <button
                  onClick={(e) => onStartEdit(e, session.session_id, session.title)}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                >
                  <PencilIcon className="h-4 w-4" />
                  Rename
                </button>
                <button
                  onClick={(e) => onDuplicate(e, session.session_id)}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                >
                  <DocumentDuplicateIcon className="h-4 w-4" />
                  Duplicate
                </button>
                <button
                  onClick={(e) => onOpenTransfer(e, session.session_id, 'move')}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                >
                  <ArrowRightOnRectangleIcon className="h-4 w-4" />
                  Move to Project
                </button>
                <button
                  onClick={(e) => onOpenTransfer(e, session.session_id, 'copy')}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                >
                  <DocumentDuplicateIcon className="h-4 w-4" />
                  Copy to Project
                </button>
                <button
                  onClick={(e) => onExport(e, session.session_id)}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                >
                  <ArrowDownTrayIcon className="h-4 w-4" />
                  Export
                </button>
                <div className="border-t border-gray-300 dark:border-gray-600 my-1"></div>
                <div className="px-2 py-1 text-xs text-gray-500 dark:text-gray-400 uppercase">
                  Move to Folder
                </div>
                <button
                  onClick={() => onMoveToFolder(session.session_id, null)}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600"
                >
                  Ungrouped
                </button>
                {folders.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => onMoveToFolder(session.session_id, f.id)}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 flex items-center gap-2"
                  >
                    <FolderIcon className="h-4 w-4 text-amber-500" />
                    {f.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={(e) => onDelete(session.session_id, e)}
            className="p-1 text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
            title="Delete conversation"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
