/**
 * FileViewer - File content editor with CodeMirror
 */

import React, { useState, useEffect } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { html } from '@codemirror/lang-html';
import { css } from '@codemirror/lang-css';
import { json } from '@codemirror/lang-json';
import { markdown } from '@codemirror/lang-markdown';
import { EditorView } from '@codemirror/view';
import type { FileContent } from '../../../types/project';
import { Breadcrumb } from './Breadcrumb';
import { writeFile } from '../../../services/api';

interface FileViewerProps {
  projectId: string;
  projectName: string;
  content: FileContent | null;
  loading: boolean;
  error: string | null;
  onContentSaved?: () => void;
}

const getLanguageExtension = (path: string) => {
  const ext = path.split('.').pop()?.toLowerCase() || '';

  const languageMap: Record<string, any> = {
    'py': python(),
    'ts': javascript({ typescript: true }),
    'tsx': javascript({ typescript: true, jsx: true }),
    'js': javascript(),
    'jsx': javascript({ jsx: true }),
    'json': json(),
    'html': html(),
    'css': css(),
    'md': markdown(),
  };

  return languageMap[ext] || [];
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const FileViewer: React.FC<FileViewerProps> = ({
  projectId,
  projectName,
  content,
  loading,
  error,
  onContentSaved
}) => {
  const [value, setValue] = useState<string>('');
  const [originalContent, setOriginalContent] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Line wrapping setting (default: true, persisted in localStorage)
  const [lineWrapping, setLineWrapping] = useState<boolean>(() => {
    const stored = localStorage.getItem('editor-line-wrapping');
    return stored !== null ? stored === 'true' : true;
  });

  // Persist line wrapping setting
  useEffect(() => {
    localStorage.setItem('editor-line-wrapping', lineWrapping.toString());
  }, [lineWrapping]);

  // Sync content when file changes
  useEffect(() => {
    if (content) {
      setValue(content.content);
      setOriginalContent(content.content);
      setSaveError(null);
      setSaveSuccess(false);
    }
  }, [content]);

  // Check if content has unsaved changes
  const hasUnsavedChanges = value !== originalContent;

  // Save handler
  const handleSave = async () => {
    if (!content || !hasUnsavedChanges) return;

    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      await writeFile(projectId, content.path, value, content.encoding);
      setOriginalContent(value);
      setSaveSuccess(true);

      // Clear success message after 2 seconds
      setTimeout(() => setSaveSuccess(false), 2000);

      if (onContentSaved) {
        onContentSaved();
      }
    } catch (err: any) {
      setSaveError(err.response?.data?.detail || err.message || 'Failed to save file');
    } finally {
      setSaving(false);
    }
  };

  // Cancel handler
  const handleCancel = () => {
    setValue(originalContent);
    setSaveError(null);
    setSaveSuccess(false);
  };

  // Ctrl+S handler
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [value, originalContent, content, projectId]);

  // Detect dark mode from DOM
  const isDarkMode = document.documentElement.classList.contains('dark');

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-red-600 dark:text-red-400">{error}</div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-white dark:bg-gray-900">
        <p className="text-gray-500 dark:text-gray-400 mb-2">Select a file to view</p>
      </div>
    );
  }

  const language = getLanguageExtension(content.path);

  // Build extensions array with conditional line wrapping
  const extensions = [language];
  if (lineWrapping) {
    extensions.push(EditorView.lineWrapping);
  }

  return (
    <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 overflow-hidden min-w-0">
      {/* Header */}
      <div className="border-b border-gray-300 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800">
        <Breadcrumb projectName={projectName} filePath={content.path} />
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
            <span>{formatFileSize(content.size)}</span>
            <span>{content.encoding}</span>
            <span>{content.mime_type}</span>
          </div>

          {/* Status indicators and settings */}
          <div className="flex items-center gap-4">
            {/* Line wrapping toggle */}
            <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
              <input
                type="checkbox"
                checked={lineWrapping}
                onChange={(e) => setLineWrapping(e.target.checked)}
                className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-0 bg-white dark:bg-gray-700"
              />
              <span>Wrap lines</span>
            </label>

            {/* Status indicators */}
            <div className="flex items-center gap-2">
              {hasUnsavedChanges && (
                <span className="text-xs text-yellow-600 dark:text-yellow-400">
                  Unsaved changes
                </span>
              )}
              {saveSuccess && (
                <span className="text-xs text-green-600 dark:text-green-400">
                  Saved successfully
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 overflow-auto w-full min-w-0">
        <CodeMirror
          value={value}
          height="100%"
          theme={isDarkMode ? 'dark' : 'light'}
          extensions={extensions}
          onChange={(val) => setValue(val)}
          basicSetup={{
            lineNumbers: true,
            highlightActiveLineGutter: true,
            highlightSpecialChars: true,
            foldGutter: true,
            drawSelection: true,
            dropCursor: true,
            allowMultipleSelections: true,
            indentOnInput: true,
            syntaxHighlighting: true,
            bracketMatching: true,
            closeBrackets: true,
            autocompletion: true,
            rectangularSelection: true,
            crosshairCursor: true,
            highlightActiveLine: true,
            highlightSelectionMatches: true,
            closeBracketsKeymap: true,
            searchKeymap: true,
            foldKeymap: true,
            completionKeymap: true,
            lintKeymap: true,
          }}
        />
      </div>

      {/* Save/Cancel buttons */}
      <div className="border-t border-gray-300 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800">
        {saveError && (
          <div className="mb-3 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-800 dark:text-red-200">
            {saveError}
          </div>
        )}
        <div className="flex justify-between items-center">
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Press Ctrl+S to save
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCancel}
              disabled={!hasUnsavedChanges || saving}
              className="px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-400 dark:disabled:text-gray-600 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!hasUnsavedChanges || saving}
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
