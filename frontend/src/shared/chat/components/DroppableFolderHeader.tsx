/**
 * DroppableFolderHeader - Draggable and droppable folder header component
 */

import React from 'react';
import {
  FolderIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  PencilIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import type { Folder } from '../../../types/folder';

interface DroppableFolderHeaderProps {
  folder: Folder;
  sessionCount: number;
  isCollapsed: boolean;
  isDropTarget: boolean;
  onToggle: () => void;
  onRename: () => void;
  onDelete: () => void;
}

export const DroppableFolderHeader: React.FC<DroppableFolderHeaderProps> = ({
  folder,
  sessionCount,
  isCollapsed,
  isDropTarget,
  onToggle,
  onRename,
  onDelete,
}) => {
  // Make folder draggable for reordering
  const {
    attributes: dragAttributes,
    listeners: dragListeners,
    setNodeRef: setDragNodeRef,
    transform,
    isDragging,
  } = useDraggable({
    id: `folder-${folder.id}`,
    data: {
      type: 'folder',
      folderId: folder.id,
      order: folder.order,
    },
  });

  // Make folder droppable for sessions AND other folders (reordering)
  const { setNodeRef: setDropNodeRef, isOver } = useDroppable({
    id: `folder-drop-${folder.id}`,
    data: {
      type: 'folder-drop',
      folderId: folder.id,
      // Also allow folder reordering
      acceptsFolder: true,
      folderOrder: folder.order,
    },
  });

  const style = {
    transform: CSS.Translate.toString(transform),
  };

  return (
    <div
      ref={setDropNodeRef}
      className={`px-3 py-2 bg-gray-50 dark:bg-gray-800/80 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between group ${
        isOver || isDropTarget ? 'bg-blue-50 dark:bg-blue-900/20 border-2 border-blue-500' : ''
      } ${isDragging ? 'opacity-50' : ''}`}
    >
      {/* Left: Toggle button (not draggable) */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onToggle();
        }}
        className="p-1 text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
        title={isCollapsed ? 'Expand' : 'Collapse'}
      >
        {isCollapsed ? (
          <ChevronRightIcon className="h-4 w-4" />
        ) : (
          <ChevronDownIcon className="h-4 w-4" />
        )}
      </button>

      {/* Center: Folder name (draggable area) */}
      <div
        ref={setDragNodeRef}
        style={style}
        {...dragAttributes}
        {...dragListeners}
        className={`flex-1 flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mx-2 cursor-grab active:cursor-grabbing ${
          isDragging ? 'opacity-50' : ''
        }`}
      >
        <FolderIcon className="h-4 w-4 text-amber-500" />
        <span className="truncate">{folder.name}</span>
        <span className="text-xs text-gray-500">({sessionCount})</span>
      </div>

      {/* Right: Action buttons (not draggable) */}
      <div
        className="opacity-0 group-hover:opacity-100 flex items-center gap-1"
      >
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRename();
          }}
          className="p-1 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
          title="Rename"
        >
          <PencilIcon className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="p-1 text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
          title="Delete"
        >
          <TrashIcon className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
};
