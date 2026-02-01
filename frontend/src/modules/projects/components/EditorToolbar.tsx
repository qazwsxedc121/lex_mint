/**
 * EditorToolbar - Toolbar for file editor with commands and controls
 */

import React from 'react';
import {
  ArrowUturnLeftIcon,
  ArrowUturnRightIcon,
  MagnifyingGlassIcon,
  ArrowsPointingOutIcon,
  HashtagIcon,
} from '@heroicons/react/24/outline';

interface EditorToolbarProps {
  // File operations
  onSave: () => void;
  onCancel: () => void;
  hasUnsavedChanges: boolean;
  saving: boolean;
  saveSuccess: boolean;
  saveError: string | null;

  // Editor commands
  onUndo: () => void;
  onRedo: () => void;
  onFind: () => void;
  canUndo: boolean;
  canRedo: boolean;

  // View options
  lineWrapping: boolean;
  onToggleLineWrapping: (enabled: boolean) => void;
  lineNumbers: boolean;
  onToggleLineNumbers: (enabled: boolean) => void;
  fontSize: 'small' | 'medium' | 'large';
  onChangeFontSize: (size: 'small' | 'medium' | 'large') => void;

  // Status display
  cursorPosition: { line: number; col: number };
  fileInfo: { encoding: string; mimeType: string; size: string };
}

export const EditorToolbar: React.FC<EditorToolbarProps> = ({
  onSave,
  onCancel,
  hasUnsavedChanges,
  saving,
  saveSuccess,
  saveError,
  onUndo,
  onRedo,
  onFind,
  canUndo,
  canRedo,
  lineWrapping,
  onToggleLineWrapping,
  lineNumbers,
  onToggleLineNumbers,
  fontSize,
  onChangeFontSize,
  cursorPosition,
  fileInfo,
}) => {
  return (
    <div className="border-b border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
      {/* Error message */}
      {saveError && (
        <div className="mx-4 mt-4 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-800 dark:text-red-200">
          {saveError}
        </div>
      )}

      {/* Toolbar */}
      <div className="p-2 flex items-center gap-1 text-xs flex-wrap">
        {/* Group 1: File Operations */}
        <div className="flex items-center gap-1 border-r border-gray-300 dark:border-gray-600 pr-3 mr-2">
          <button
            title="Save (Ctrl+S)"
            onClick={onSave}
            disabled={!hasUnsavedChanges || saving}
            className="px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:cursor-not-allowed disabled:text-gray-500"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button
            title="Cancel changes"
            onClick={onCancel}
            disabled={!hasUnsavedChanges || saving}
            className="px-3 py-1.5 rounded text-xs border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-400 dark:disabled:text-gray-600 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          {hasUnsavedChanges && !saveSuccess && (
            <span className="text-yellow-600 dark:text-yellow-400 ml-1" title="Unsaved changes">
              ●
            </span>
          )}
          {saveSuccess && (
            <span className="text-green-600 dark:text-green-400 ml-1">
              Saved
            </span>
          )}
        </div>

        {/* Group 2: Editor Commands */}
        <div className="flex items-center gap-1 border-r border-gray-300 dark:border-gray-600 pr-3 mr-2">
          <button
            title="Undo (Ctrl+Z)"
            disabled={!canUndo}
            onClick={onUndo}
            className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ArrowUturnLeftIcon className="h-4 w-4 text-gray-700 dark:text-gray-300" />
          </button>
          <button
            title="Redo (Ctrl+Y)"
            disabled={!canRedo}
            onClick={onRedo}
            className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ArrowUturnRightIcon className="h-4 w-4 text-gray-700 dark:text-gray-300" />
          </button>
          <button
            title="Find (Ctrl+F)"
            onClick={onFind}
            className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
          >
            <MagnifyingGlassIcon className="h-4 w-4 text-gray-700 dark:text-gray-300" />
          </button>
        </div>

        {/* Group 3: View Options */}
        <div className="flex items-center gap-1 border-r border-gray-300 dark:border-gray-600 pr-3 mr-2">
          <button
            title="Toggle line wrapping"
            onClick={() => onToggleLineWrapping(!lineWrapping)}
            className={`p-1.5 rounded ${
              lineWrapping
                ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
            }`}
          >
            <ArrowsPointingOutIcon className="h-4 w-4" />
          </button>
          <button
            title="Toggle line numbers"
            onClick={() => onToggleLineNumbers(!lineNumbers)}
            className={`p-1.5 rounded ${
              lineNumbers
                ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
            }`}
          >
            <HashtagIcon className="h-4 w-4" />
          </button>
          <select
            title="Font size"
            value={fontSize}
            onChange={(e) => onChangeFontSize(e.target.value as 'small' | 'medium' | 'large')}
            className="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          >
            <option value="small">Small</option>
            <option value="medium">Medium</option>
            <option value="large">Large</option>
          </select>
        </div>

        {/* Group 4: Status Display */}
        <div className="flex items-center gap-3 text-gray-600 dark:text-gray-400 ml-auto">
          <span title="Cursor position">
            Ln {cursorPosition.line}:Col {cursorPosition.col}
          </span>
          <span title="File encoding">
            {fileInfo.encoding}
          </span>
          <span title="MIME type">
            {fileInfo.mimeType}
          </span>
          <span title="File size">
            {fileInfo.size}
          </span>
        </div>
      </div>
    </div>
  );
};
