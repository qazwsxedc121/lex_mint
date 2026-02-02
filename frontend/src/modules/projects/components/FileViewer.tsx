/**
 * FileViewer - File content editor with CodeMirror
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { html } from '@codemirror/lang-html';
import { css } from '@codemirror/lang-css';
import { json } from '@codemirror/lang-json';
import { markdown } from '@codemirror/lang-markdown';
import { EditorView } from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { undo, redo, undoDepth, redoDepth } from '@codemirror/commands';
import { openSearchPanel, search } from '@codemirror/search';
import type { FileContent } from '../../../types/project';
import { Breadcrumb } from './Breadcrumb';
import { writeFile } from '../../../services/api';
import { EditorToolbar } from './EditorToolbar';

interface FileViewerProps {
  projectId: string;
  projectName: string;
  content: FileContent | null;
  loading: boolean;
  error: string | null;
  onContentSaved?: () => void;
  chatSidebarOpen: boolean;
  onToggleChatSidebar: () => void;
  onEditorReady?: (actions: { insertContent: (text: string) => void }) => void;
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
  onContentSaved,
  chatSidebarOpen,
  onToggleChatSidebar,
  onEditorReady,
}) => {
  const [value, setValue] = useState<string>('');
  const [originalContent, setOriginalContent] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Editor view reference
  const editorViewRef = useRef<EditorView | null>(null);

  // Line wrapping setting (default: true, persisted in localStorage)
  const [lineWrapping, setLineWrapping] = useState<boolean>(() => {
    const stored = localStorage.getItem('editor-line-wrapping');
    return stored !== null ? stored === 'true' : true;
  });

  // Line numbers setting (default: true, persisted in localStorage)
  const [lineNumbers, setLineNumbers] = useState<boolean>(() => {
    const stored = localStorage.getItem('editor-line-numbers');
    return stored !== null ? stored === 'true' : true;
  });

  // Font size setting (default: medium, persisted in localStorage)
  const [fontSize, setFontSize] = useState<'small' | 'medium' | 'large'>(() => {
    const stored = localStorage.getItem('editor-font-size');
    return (stored as 'small' | 'medium' | 'large') || 'medium';
  });

  // Cursor position
  const [cursorPosition, setCursorPosition] = useState({ line: 1, col: 1 });

  // Undo/redo state
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  // Persist line wrapping setting
  useEffect(() => {
    localStorage.setItem('editor-line-wrapping', lineWrapping.toString());
  }, [lineWrapping]);

  // Persist line numbers setting
  useEffect(() => {
    localStorage.setItem('editor-line-numbers', lineNumbers.toString());
  }, [lineNumbers]);

  // Persist font size setting
  useEffect(() => {
    localStorage.setItem('editor-font-size', fontSize);
  }, [fontSize]);

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

  // Update undo/redo state
  const updateUndoRedoState = useCallback(() => {
    if (editorViewRef.current) {
      const state = editorViewRef.current.state;
      setCanUndo(undoDepth(state) > 0);
      setCanRedo(redoDepth(state) > 0);
    }
  }, []);

  // Insert content at cursor position
  const insertContentAtCursor = useCallback((content: string) => {
    if (!editorViewRef.current) return;

    const view = editorViewRef.current;
    const pos = view.state.selection.main.head;

    view.dispatch({
      changes: { from: pos, insert: content },
      selection: { anchor: pos + content.length }
    });

    // No need to manually call setValue - CodeMirror's onChange will handle it
    // Calling setValue here causes unnecessary re-render and flickering

    // Focus the editor
    view.focus();
  }, []);

  // Command handlers
  const handleUndo = useCallback(() => {
    if (editorViewRef.current) {
      undo(editorViewRef.current);
      updateUndoRedoState();
    }
  }, [updateUndoRedoState]);

  const handleRedo = useCallback(() => {
    if (editorViewRef.current) {
      redo(editorViewRef.current);
      updateUndoRedoState();
    }
  }, [updateUndoRedoState]);

  const handleFind = useCallback(() => {
    if (editorViewRef.current) {
      openSearchPanel(editorViewRef.current);
    }
  }, []);

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

  // Create cursor position tracking extension (memoized to prevent re-creation)
  const cursorPositionExtension = useMemo(() =>
    EditorView.updateListener.of((update) => {
      if (update.selectionSet) {
        const pos = update.state.selection.main.head;
        const line = update.state.doc.lineAt(pos);
        setCursorPosition({
          line: line.number,
          col: pos - line.from + 1
        });
      }
    }),
  []);

  // Create update listener for undo/redo state (memoized to prevent re-creation)
  const updateListener = useMemo(() =>
    EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        updateUndoRedoState();
      }
    }),
  [updateUndoRedoState]);

  // Create font size theme extension (memoized to prevent re-creation)
  const fontSizeTheme = useMemo(() => {
    const sizeMap = { small: '12px', medium: '14px', large: '16px' };
    return EditorView.theme({
      '&': { fontSize: sizeMap[fontSize] },
      '.cm-content': { fontSize: sizeMap[fontSize] },
      '.cm-gutters': { fontSize: sizeMap[fontSize] }
    });
  }, [fontSize]);

  // Search extension (memoized to prevent re-creation)
  const searchExtension = useMemo(() => search({ top: true }), []);

  // Line wrapping extension (memoized)
  const lineWrappingExtension = useMemo(() => EditorView.lineWrapping, []);

  // Callback for when editor is created
  const onEditorCreate = useCallback((view: EditorView, _state: EditorState) => {
    editorViewRef.current = view;
    updateUndoRedoState();

    // Notify parent immediately when editor is ready
    if (onEditorReady) {
      onEditorReady({ insertContent: insertContentAtCursor });
    }
  }, [updateUndoRedoState, onEditorReady, insertContentAtCursor]);

  // Get language extension (memoized to prevent re-creation)
  const filePath = content?.path ?? '';
  const language = useMemo(() => getLanguageExtension(filePath), [filePath]);

  // Build extensions array with conditional features (memoized to prevent re-creation)
  const extensions = useMemo(() => [
    language,
    lineWrapping && lineWrappingExtension,
    fontSizeTheme,
    cursorPositionExtension,
    updateListener,
    searchExtension,
  ].filter(Boolean), [language, lineWrapping, lineWrappingExtension, fontSizeTheme, cursorPositionExtension, updateListener, searchExtension]);

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

  return (
    <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 overflow-hidden min-w-0">
      {/* Breadcrumb */}
      <div className="border-b border-gray-300 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800">
        <Breadcrumb projectName={projectName} filePath={content.path} />
      </div>

      {/* Toolbar */}
      <EditorToolbar
        onSave={handleSave}
        onCancel={handleCancel}
        hasUnsavedChanges={hasUnsavedChanges}
        saving={saving}
        saveSuccess={saveSuccess}
        saveError={saveError}
        onUndo={handleUndo}
        onRedo={handleRedo}
        onFind={handleFind}
        canUndo={canUndo}
        canRedo={canRedo}
        lineWrapping={lineWrapping}
        onToggleLineWrapping={setLineWrapping}
        lineNumbers={lineNumbers}
        onToggleLineNumbers={setLineNumbers}
        fontSize={fontSize}
        onChangeFontSize={setFontSize}
        cursorPosition={cursorPosition}
        fileInfo={{
          encoding: content.encoding,
          mimeType: content.mime_type,
          size: formatFileSize(content.size)
        }}
        chatSidebarOpen={chatSidebarOpen}
        onToggleChatSidebar={onToggleChatSidebar}
      />

      {/* Editor */}
      <div className="flex-1 overflow-auto w-full min-w-0">
        <CodeMirror
          value={value}
          height="100%"
          theme={isDarkMode ? 'dark' : 'light'}
          extensions={extensions}
          onChange={(val) => setValue(val)}
          onCreateEditor={onEditorCreate}
          basicSetup={{
            lineNumbers: lineNumbers,
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
    </div>
  );
};
