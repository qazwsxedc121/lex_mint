/**
 * EditorToolbar - Toolbar for file editor with commands and controls
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  ArrowUturnLeftIcon,
  ArrowUturnRightIcon,
  MagnifyingGlassIcon,
  ArrowsPointingOutIcon,
  HashtagIcon,
  EyeIcon,
  PencilSquareIcon,
  ArrowUpOnSquareIcon,
  CloudArrowUpIcon,
  DocumentTextIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { ChatToggleButton } from './ChatToggleButton';

interface EditorToolbarProps {
  // File operations
  onSave: () => void;
  onCancel: () => void;
  hasUnsavedChanges: boolean;
  saving: boolean;
  saveSuccess: boolean;
  saveError: string | null;
  saveConflictState?: 'none' | 'detected' | 'remoteLoaded';
  conflictBusy?: boolean;
  onLoadLatestAfterConflict?: () => void;
  onRestoreConflictDraft?: () => void;
  onCopyConflictDraft?: () => void;

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
  isMarkdownFile?: boolean;
  markdownViewMode?: 'edit' | 'preview';
  onSetMarkdownViewMode?: (mode: 'edit' | 'preview') => void;
  autoSaveBeforeAgentSend: boolean;
  onToggleAutoSaveBeforeAgentSend: (enabled: boolean) => void;

  // Status display
  cursorPosition: { line: number; col: number };
  fileInfo: { encoding: string; mimeType: string; size: string };

  // Chat sidebar toggle
  chatSidebarOpen: boolean;
  onToggleChatSidebar: () => void;

  // Insert editor content to chat
  onInsertToChat: () => void;
  insertToChatDisabled: boolean;
  insertToChatTitle: string;

  // Inline rewrite
  onInlineRewrite: () => void;
  inlineRewriteDisabled: boolean;
  inlineRewriteTitle: string;

  // Project workflow
  onProjectWorkflow: () => void;
  projectWorkflowDisabled: boolean;
  projectWorkflowTitle: string;
}

export const EditorToolbar: React.FC<EditorToolbarProps> = ({
  onSave,
  onCancel,
  hasUnsavedChanges,
  saving,
  saveSuccess,
  saveError,
  saveConflictState = 'none',
  conflictBusy = false,
  onLoadLatestAfterConflict,
  onRestoreConflictDraft,
  onCopyConflictDraft,
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
  isMarkdownFile = false,
  markdownViewMode = 'edit',
  onSetMarkdownViewMode,
  autoSaveBeforeAgentSend,
  onToggleAutoSaveBeforeAgentSend,
  cursorPosition,
  fileInfo,
  chatSidebarOpen,
  onToggleChatSidebar,
  onInsertToChat,
  insertToChatDisabled,
  insertToChatTitle,
  onInlineRewrite,
  inlineRewriteDisabled,
  inlineRewriteTitle,
  onProjectWorkflow,
  projectWorkflowDisabled,
  projectWorkflowTitle,
}) => {
  const { t } = useTranslation('projects');

  return (
    <div className="border-b border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
      {/* Error message */}
      {saveError && (
        <div className="mx-4 mt-4 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-800 dark:text-red-200 space-y-2">
          <div>{saveError}</div>
          {saveConflictState !== 'none' && (
            <div className="flex items-center gap-2 flex-wrap">
              {onLoadLatestAfterConflict && (
                <button
                  type="button"
                  onClick={onLoadLatestAfterConflict}
                  disabled={conflictBusy}
                  className="px-2 py-1 rounded bg-red-700 hover:bg-red-800 text-white disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {conflictBusy ? t('editor.conflictLoadingLatest') : t('editor.conflictLoadLatest')}
                </button>
              )}
              {saveConflictState === 'remoteLoaded' && onRestoreConflictDraft && (
                <button
                  type="button"
                  onClick={onRestoreConflictDraft}
                  disabled={conflictBusy}
                  className="px-2 py-1 rounded border border-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {t('editor.conflictRestoreDraft')}
                </button>
              )}
              {onCopyConflictDraft && (
                <button
                  type="button"
                  onClick={onCopyConflictDraft}
                  disabled={conflictBusy}
                  className="px-2 py-1 rounded border border-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {t('editor.conflictCopyDraft')}
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Toolbar */}
      <div className="p-2 flex items-center gap-1 text-xs flex-wrap">
        {/* Group 1: File Operations */}
        <div className="flex items-center gap-1 border-r border-gray-300 dark:border-gray-600 pr-3 mr-2">
          <button
            title={t('editor.save')}
            onClick={onSave}
            disabled={!hasUnsavedChanges || saving}
            className="px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:cursor-not-allowed disabled:text-gray-500"
          >
            {saving ? t('editor.saving') : t('common:save')}
          </button>
          <button
            title={t('editor.cancelChanges')}
            onClick={onCancel}
            disabled={!hasUnsavedChanges || saving}
            className="px-3 py-1.5 rounded text-xs border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-400 dark:disabled:text-gray-600 disabled:cursor-not-allowed"
          >
            {t('common:cancel')}
          </button>
          {hasUnsavedChanges && !saveSuccess && (
            <span className="text-yellow-600 dark:text-yellow-400 ml-1" title={t('editor.unsavedChanges')}>
              ●
            </span>
          )}
          {saveSuccess && (
            <span className="text-green-600 dark:text-green-400 ml-1">
              {t('editor.saved')}
            </span>
          )}
        </div>

        {/* Group 2: Editor Commands */}
        <div className="flex items-center gap-1 border-r border-gray-300 dark:border-gray-600 pr-3 mr-2">
          <button
            title={t('editor.undo')}
            disabled={!canUndo}
            onClick={onUndo}
            className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ArrowUturnLeftIcon className="h-4 w-4 text-gray-700 dark:text-gray-300" />
          </button>
          <button
            title={t('editor.redo')}
            disabled={!canRedo}
            onClick={onRedo}
            className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ArrowUturnRightIcon className="h-4 w-4 text-gray-700 dark:text-gray-300" />
          </button>
          <button
            title={t('editor.find')}
            onClick={onFind}
            className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
          >
            <MagnifyingGlassIcon className="h-4 w-4 text-gray-700 dark:text-gray-300" />
          </button>
        </div>

        {/* Group 3: View Options */}
        <div className="flex items-center gap-1 border-r border-gray-300 dark:border-gray-600 pr-3 mr-2">
          <button
            title={t('editor.toggleWrap')}
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
            title={t('editor.toggleLineNumbers')}
            onClick={() => onToggleLineNumbers(!lineNumbers)}
            className={`p-1.5 rounded ${
              lineNumbers
                ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
            }`}
          >
            <HashtagIcon className="h-4 w-4" />
          </button>
          {isMarkdownFile && onSetMarkdownViewMode && (
            <div
              className="inline-flex items-center overflow-hidden rounded-md border border-gray-300 bg-white dark:border-gray-600 dark:bg-gray-900"
              role="group"
              aria-label={t('fileViewer.markdownModePreview')}
            >
              <button
                type="button"
                title={t('fileViewer.markdownModeEdit')}
                data-name="markdown-view-mode-edit"
                onClick={() => onSetMarkdownViewMode('edit')}
                aria-pressed={markdownViewMode === 'edit'}
                className={`p-1.5 ${
                  markdownViewMode === 'edit'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                }`}
              >
                <PencilSquareIcon className="h-4 w-4" />
              </button>
              <div className="h-5 w-px bg-gray-300 dark:bg-gray-600" />
              <button
                type="button"
                title={t('fileViewer.markdownModePreview')}
                data-name="markdown-view-mode-preview"
                onClick={() => onSetMarkdownViewMode('preview')}
                aria-pressed={markdownViewMode === 'preview'}
                className={`p-1.5 ${
                  markdownViewMode === 'preview'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                }`}
              >
                <EyeIcon className="h-4 w-4" />
              </button>
            </div>
          )}
          <select
            title={t('editor.fontSize')}
            value={fontSize}
            onChange={(e) => onChangeFontSize(e.target.value as 'small' | 'medium' | 'large')}
            className="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          >
            <option value="small">{t('editor.fontSizeSmall')}</option>
            <option value="medium">{t('editor.fontSizeMedium')}</option>
            <option value="large">{t('editor.fontSizeLarge')}</option>
          </select>
        </div>

        {/* Group 4: Chat Toggle */}
        <div className="flex items-center gap-1 border-r border-gray-300 dark:border-gray-600 pr-3 mr-2">
          <button
            type="button"
            title={`${t('editor.agentSend.autoSaveLabel')} - ${t('editor.agentSend.autoSaveHelp')}`}
            onClick={() => onToggleAutoSaveBeforeAgentSend(!autoSaveBeforeAgentSend)}
            aria-label={t('editor.agentSend.autoSaveLabel')}
            aria-pressed={autoSaveBeforeAgentSend}
            data-name="editor-auto-save-before-send-toggle"
            className={`p-1.5 rounded ${
              autoSaveBeforeAgentSend
                ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
            }`}
          >
            <CloudArrowUpIcon className="h-4 w-4" />
          </button>
          <button
            title={inlineRewriteTitle}
            onClick={onInlineRewrite}
            disabled={inlineRewriteDisabled}
            data-name="editor-inline-rewrite-button"
            className={`p-1.5 rounded ${
              inlineRewriteDisabled
                ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed opacity-60'
                : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
            }`}
          >
            <SparklesIcon className="h-4 w-4" />
          </button>
          <button
            title={projectWorkflowTitle}
            onClick={onProjectWorkflow}
            disabled={projectWorkflowDisabled}
            data-name="editor-project-workflow-button"
            className={`p-1.5 rounded ${
              projectWorkflowDisabled
                ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed opacity-60'
                : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
            }`}
          >
            <DocumentTextIcon className="h-4 w-4" />
          </button>
          <button
            title={insertToChatTitle}
            onClick={onInsertToChat}
            disabled={insertToChatDisabled}
            data-name="editor-insert-chat-button"
            className={`p-1.5 rounded ${
              insertToChatDisabled
                ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed opacity-60'
                : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
            }`}
          >
            <ArrowUpOnSquareIcon className="h-4 w-4" />
          </button>
          <ChatToggleButton
            isOpen={chatSidebarOpen}
            onToggle={onToggleChatSidebar}
          />
        </div>

        {/* Group 5: Status Display */}
        <div className="flex items-center gap-3 text-gray-600 dark:text-gray-400 ml-auto">
          <span>
            {t('editor.cursorPosition', { line: cursorPosition.line, col: cursorPosition.col })}
          </span>
          <span>
            {fileInfo.encoding}
          </span>
          <span>
            {fileInfo.mimeType}
          </span>
          <span>
            {fileInfo.size}
          </span>
        </div>
      </div>
    </div>
  );
};
