/**
 * FileViewer - File content editor with CodeMirror
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { html } from '@codemirror/lang-html';
import { css } from '@codemirror/lang-css';
import { json } from '@codemirror/lang-json';
import { markdown } from '@codemirror/lang-markdown';
import { EditorView } from '@codemirror/view';
import { undo, redo, undoDepth, redoDepth } from '@codemirror/commands';
import { openSearchPanel, search } from '@codemirror/search';
import type { FileContent } from '../../../types/project';
import { readFile, writeFile } from '../../../services/api';
import { useChatComposer, useChatServices } from '../../../shared/chat';
import { useEditorPreferences } from '../hooks/useEditorPreferences';
import { useGlobalHotkey } from '../hooks/useGlobalHotkey';
import { useProjectNotice } from '../hooks/useProjectNotice';
import { useInlineRewriteController } from '../hooks/useInlineRewriteController';
import { useProjectWorkspaceStore } from '../../../stores/projectWorkspaceStore';
import { getProjectWorkspacePath } from '../workspace';
import { buildFileAgentContextItem } from '../agentContext';
import { FileViewerBreadcrumbBar } from './FileViewerBreadcrumbBar';
import { FileViewerEditorContent } from './FileViewerEditorContent';
import { normalizeMathDelimiters } from '../../../shared/chat/utils/markdownMath';
import { extractSvgBlocks } from '../../../shared/chat/utils/svgMarkdown';

const CHAT_CONTEXT_MAX_CHARS = 6000;

interface SaveConflictState {
  code: string;
  localDraft: string;
  remoteLoaded: boolean;
}

export interface BeforeAgentSendResult {
  proceed: boolean;
  reason?: string;
  activeFilePath?: string;
  activeFileHash?: string;
}

export type BeforeAgentSendHandler = () => Promise<BeforeAgentSendResult>;

interface FileViewerProps {
  projectId: string;
  projectName: string;
  content: FileContent | null;
  loading: boolean;
  error: string | null;
  onContentSaved?: () => void;
  onRefreshProject?: () => Promise<void> | void;
  chatSidebarOpen: boolean;
  fileTreeOpen: boolean;
  onToggleChatSidebar: () => void;
  onToggleFileTree: () => void;
  onEditorReady?: (actions: { insertContent: (text: string) => void }) => void;
  onRegisterBeforeAgentSend?: (handler: BeforeAgentSendHandler | null) => void;
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

const getLanguageTag = (path: string): string => {
  const ext = path.split('.').pop()?.toLowerCase() || '';
  const languageMap: Record<string, string> = {
    'py': 'python',
    'ts': 'ts',
    'tsx': 'tsx',
    'js': 'js',
    'jsx': 'jsx',
    'json': 'json',
    'html': 'html',
    'css': 'css',
    'md': 'markdown',
    'yml': 'yaml',
    'yaml': 'yaml',
    'txt': 'text',
  };

  return languageMap[ext] || ext;
};

const isMarkdownFilePath = (path: string): boolean => {
  const ext = path.split('.').pop()?.toLowerCase() || '';
  return ext === 'md' || ext === 'markdown';
};

const normalizeMarkdownFrontmatter = (text: string): string => {
  const normalized = text.replace(/\r\n/g, '\n');
  const match = normalized.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!match) {
    return normalized;
  }

  const body = normalized.slice(match[0].length).replace(/^\s+/, '');
  return `\`\`\`yaml\n${match[1].trim()}\n\`\`\`\n\n${body}`;
};

const normalizeMermaidSyntax = (text: string): string =>
  text.replace(/```mermaid\s*\n([\s\S]*?)```/gi, (_match, code: string) => {
    const normalizedCode = code
      .replace(/[“”]/g, '"')
      .replace(/[‘’]/g, "'")
      .trimEnd();

    return `\`\`\`mermaid\n${normalizedCode}\n\`\`\``;
  });

const prepareMarkdownForPreview = (text: string) =>
  normalizeMathDelimiters(
    extractSvgBlocks(normalizeMermaidSyntax(normalizeMarkdownFrontmatter(text)))
  );

const buildAttachmentFilename = (filePath: string, isSelection: boolean, startLine: number, endLine: number) => {
  const normalized = filePath.replace(/\\/g, '/');
  const baseName = normalized.split('/').pop() || 'context.txt';
  const dotIndex = baseName.lastIndexOf('.');
  const hasExt = dotIndex > 0;
  const stem = hasExt ? baseName.slice(0, dotIndex) : baseName;
  const ext = hasExt ? baseName.slice(dotIndex + 1) : 'txt';
  const rangeLabel = isSelection ? `lines-${startLine}-${endLine}` : 'full';
  return `${stem}.${rangeLabel}.${ext}`;
};

const countLines = (text: string) => {
  const lines = text.split('\n').length;
  return lines > 0 ? lines : 1;
};

const normalizeProjectPath = (pathValue: string) => pathValue.replace(/\\/g, '/');

export const FileViewer: React.FC<FileViewerProps> = ({
  projectId,
  projectName,
  content,
  loading,
  error,
  onContentSaved,
  onRefreshProject,
  chatSidebarOpen,
  fileTreeOpen,
  onToggleChatSidebar,
  onToggleFileTree,
  onEditorReady,
  onRegisterBeforeAgentSend,
}) => {
  const { t } = useTranslation('projects');
  const navigate = useNavigate();
  const [markdownViewMode, setMarkdownViewMode] = useState<'edit' | 'preview'>('edit');
  const [value, setValue] = useState<string>('');
  const [originalContent, setOriginalContent] = useState<string>('');
  const [originalHash, setOriginalHash] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveConflict, setSaveConflict] = useState<SaveConflictState | null>(null);
  const [conflictBusy, setConflictBusy] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isInsertingToChat, setIsInsertingToChat] = useState(false);
  const [refreshingProject, setRefreshingProject] = useState(false);
  const {
    lineWrapping,
    setLineWrapping,
    lineNumbers,
    setLineNumbers,
    fontSize,
    setFontSize,
    autoSaveBeforeAgentSend,
    setAutoSaveBeforeAgentSend,
  } = useEditorPreferences();
  const { notice, showError: showNoticeError, clearNotice } = useProjectNotice();
  const { queueWorkflowLaunch, addAgentContextItems } = useProjectWorkspaceStore();

  const { currentSessionId, createSession, createTemporarySession, navigation } = useChatServices();
  const chatComposer = useChatComposer();

  // Editor view reference
  const editorViewRef = useRef<EditorView | null>(null);
  const pendingJumpRef = useRef<{ filePath: string; line: number } | null>(null);

  // Cursor position
  const [cursorPosition, setCursorPosition] = useState({ line: 1, col: 1 });

  // Undo/redo state
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  // Sync content when file changes
  useEffect(() => {
    if (content) {
      setValue(content.content);
      setOriginalContent(content.content);
      setOriginalHash(content.content_hash || null);
      setMarkdownViewMode('edit');
      setSaveError(null);
      setSaveConflict(null);
      setConflictBusy(false);
      setSaveSuccess(false);
    }
  }, [content]);

  // Check if content has unsaved changes
  const hasUnsavedChanges = value !== originalContent;
  const inlineRewrite = useInlineRewriteController({
    projectId,
    content,
    value,
    editorViewRef,
    currentSessionId,
    createTemporarySession,
    navigation,
    queueWorkflowLaunch,
  });

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

  const ensureChatSession = useCallback(async () => {
    if (currentSessionId) {
      return currentSessionId;
    }

    try {
      const newSessionId = await createSession();
      navigation?.navigateToSession(newSessionId);
      return newSessionId;
    } catch (err) {
      console.error('Failed to create chat session:', err);
      showNoticeError(t('chat.createFailed'));
      return null;
    }
  }, [currentSessionId, createSession, navigation, showNoticeError, t]);

  const getEditorContext = useCallback(() => {
    if (!content) return null;

    const view = editorViewRef.current;
    const filePath = content.path;
    const language = getLanguageTag(filePath);

    if (view) {
      const selection = view.state.selection.main;
      if (!selection.empty) {
        const selectedText = view.state.doc.sliceString(selection.from, selection.to);
        const startLine = view.state.doc.lineAt(selection.from).number;
        const endLine = view.state.doc.lineAt(selection.to).number;
        return {
          text: selectedText,
          startLine,
          endLine,
          language,
          filePath,
          isSelection: true,
        };
      }
    }

    const fullText = value;
    const totalLines = view ? view.state.doc.lines : countLines(fullText);
    return {
      text: fullText,
      startLine: 1,
      endLine: totalLines,
      language,
      filePath,
      isSelection: false,
    };
  }, [content, value]);

  const handleInsertToChat = useCallback(async () => {
    if (!content || isInsertingToChat) return;

    setIsInsertingToChat(true);
    try {
      if (!chatSidebarOpen) {
        onToggleChatSidebar();
      }

      const sessionId = await ensureChatSession();
      if (!sessionId) return;

      const contextInfo = getEditorContext();
      if (!contextInfo) return;

      const isLong = contextInfo.text.length > CHAT_CONTEXT_MAX_CHARS;

      if (isLong) {
        const filename = buildAttachmentFilename(
          contextInfo.filePath,
          contextInfo.isSelection,
          contextInfo.startLine,
          contextInfo.endLine
        );
        await chatComposer.attachTextFile({
          filename,
          content: contextInfo.text,
          mimeType: 'text/plain',
        });
        await chatComposer.addBlock({
          title: `Context: ${contextInfo.filePath} lines ${contextInfo.startLine}-${contextInfo.endLine}`,
          content: '',
          collapsed: true,
          kind: 'context',
          language: contextInfo.language,
          source: {
            filePath: contextInfo.filePath,
            startLine: contextInfo.startLine,
            endLine: contextInfo.endLine,
          },
          isAttachmentNote: true,
          attachmentFilename: filename,
        });
      } else {
        await chatComposer.addBlock({
          title: `Context: ${contextInfo.filePath} lines ${contextInfo.startLine}-${contextInfo.endLine}`,
          content: contextInfo.text,
          collapsed: true,
          kind: 'context',
          language: contextInfo.language,
          source: {
            filePath: contextInfo.filePath,
            startLine: contextInfo.startLine,
            endLine: contextInfo.endLine,
          },
        });
      }

      await chatComposer.focus();
    } catch (err) {
      console.error('Failed to insert editor content into chat:', err);
      showNoticeError(t('fileViewer.insertFailed'));
    } finally {
      setIsInsertingToChat(false);
    }
  }, [
    content,
    isInsertingToChat,
    chatSidebarOpen,
    onToggleChatSidebar,
    ensureChatSession,
    getEditorContext,
    chatComposer,
    showNoticeError,
    t,
  ]);

  const handleSendToAgent = useCallback(() => {
    if (!content) {
      return;
    }

    const contextInfo = getEditorContext();
    if (!contextInfo) {
      return;
    }

    addAgentContextItems(projectId, [buildFileAgentContextItem(contextInfo)]);
    navigate(getProjectWorkspacePath(projectId, 'agent'));
  }, [addAgentContextItems, content, getEditorContext, navigate, projectId]);

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

  const jumpToLine = useCallback((lineNumber: number) => {
    if (!editorViewRef.current) {
      return;
    }
    const view = editorViewRef.current;
    const totalLines = Math.max(1, view.state.doc.lines);
    const safeLine = Math.max(1, Math.min(lineNumber, totalLines));
    const line = view.state.doc.line(safeLine);
    view.dispatch({
      selection: { anchor: line.from },
      scrollIntoView: true,
    });
    view.focus();
  }, []);

  const saveCurrentFile = useCallback(async (): Promise<{ ok: boolean; contentHash?: string }> => {
    if (!content) {
      return { ok: false };
    }
    if (!hasUnsavedChanges) {
      return { ok: true, contentHash: originalHash || undefined };
    }

    setSaving(true);
    setSaveError(null);
    setSaveConflict(null);
    setSaveSuccess(false);

    try {
      const saved = await writeFile(
        projectId,
        content.path,
        value,
        content.encoding,
        originalHash || undefined
      );
      setOriginalContent(saved.content);
      setOriginalHash(saved.content_hash || null);
      setSaveConflict(null);
      setSaveSuccess(true);

      // Clear success message after 2 seconds
      setTimeout(() => setSaveSuccess(false), 2000);

      if (onContentSaved) {
        onContentSaved();
      }
      return { ok: true, contentHash: saved.content_hash || undefined };
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === 'string') {
        setSaveError(detail);
      } else if (detail && typeof detail === 'object') {
        const code = typeof detail.code === 'string' ? detail.code : '';
        const message = typeof detail.message === 'string' ? detail.message : '';
        if (code === 'HASH_MISMATCH' || code === 'FILE_MISSING') {
          setSaveConflict({
            code,
            localDraft: value,
            remoteLoaded: false,
          });
          setSaveError(t('editor.conflictDetected'));
        } else if (code && message) {
          setSaveError(`${code}: ${message}`);
        } else if (message) {
          setSaveError(message);
        } else {
          setSaveError(err?.message || 'Failed to save file');
        }
      } else {
        setSaveError(err?.message || 'Failed to save file');
      }
      return { ok: false };
    } finally {
      setSaving(false);
    }
  }, [content, hasUnsavedChanges, onContentSaved, originalHash, projectId, t, value]);

  // Save handler
  const handleSave = useCallback(async () => {
    await saveCurrentFile();
  }, [saveCurrentFile]);

  const prepareBeforeAgentSend = useCallback(async (): Promise<BeforeAgentSendResult> => {
    if (!content) {
      return { proceed: true };
    }

    if (!hasUnsavedChanges) {
      return {
        proceed: true,
        activeFilePath: content.path,
        activeFileHash: originalHash || undefined,
      };
    }

    if (autoSaveBeforeAgentSend) {
      const saved = await saveCurrentFile();
      if (!saved.ok) {
        return {
          proceed: false,
          reason: t('editor.agentSend.autoSaveFailed'),
        };
      }
      return {
        proceed: true,
        activeFilePath: content.path,
        activeFileHash: saved.contentHash,
      };
    }

    const shouldSaveFirst = window.confirm(
      t('editor.agentSend.unsavedPromptSave', { filePath: content.path })
    );
    if (shouldSaveFirst) {
      const saved = await saveCurrentFile();
      if (!saved.ok) {
        return {
          proceed: false,
          reason: t('editor.agentSend.autoSaveFailed'),
        };
      }
      return {
        proceed: true,
        activeFilePath: content.path,
        activeFileHash: saved.contentHash,
      };
    }

    const continueWithoutSaving = window.confirm(t('editor.agentSend.unsavedPromptContinue'));
    if (!continueWithoutSaving) {
      return { proceed: false };
    }

    return {
      proceed: true,
      activeFilePath: content.path,
      activeFileHash: originalHash || undefined,
    };
  }, [autoSaveBeforeAgentSend, content, hasUnsavedChanges, originalHash, saveCurrentFile, t]);

  useEffect(() => {
    if (!onRegisterBeforeAgentSend) {
      return;
    }
    onRegisterBeforeAgentSend(prepareBeforeAgentSend);
    return () => onRegisterBeforeAgentSend(null);
  }, [onRegisterBeforeAgentSend, prepareBeforeAgentSend]);

  const handleLoadLatestAfterConflict = useCallback(async () => {
    if (!content || !saveConflict || conflictBusy) {
      return;
    }
    setConflictBusy(true);
    try {
      const latest = await readFile(projectId, content.path);
      setValue(latest.content);
      setOriginalContent(latest.content);
      setOriginalHash(latest.content_hash || null);
      setSaveSuccess(false);
      setSaveError(t('editor.conflictLatestLoaded'));
      setSaveConflict((prev) => (prev ? { ...prev, remoteLoaded: true } : prev));
    } catch (err: any) {
      setSaveError(err?.response?.data?.detail || err?.message || t('fileViewer.refreshFailed'));
    } finally {
      setConflictBusy(false);
    }
  }, [conflictBusy, content, projectId, saveConflict, t]);

  const handleRestoreConflictDraft = useCallback(() => {
    if (!saveConflict || !saveConflict.remoteLoaded) {
      return;
    }
    setValue(saveConflict.localDraft);
    setSaveError(t('editor.conflictDraftRestored'));
    setSaveSuccess(false);
    setSaveConflict((prev) => (prev ? { ...prev, remoteLoaded: false } : prev));
  }, [saveConflict, t]);

  const handleCopyConflictDraft = useCallback(async () => {
    if (!saveConflict) {
      return;
    }
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(saveConflict.localDraft);
      }
      setSaveError(t('editor.conflictDraftCopied'));
    } catch {
      setSaveError(t('editor.conflictDraftCopyFailed'));
    }
  }, [saveConflict, t]);

  // Cancel handler
  const handleCancel = () => {
    setValue(originalContent);
    setSaveError(null);
    setSaveConflict(null);
    setSaveSuccess(false);
  };

  const handleRefreshProject = useCallback(async () => {
    if (!onRefreshProject || refreshingProject) {
      return;
    }

    if (hasUnsavedChanges && !window.confirm(t('fileViewer.refreshConfirmDiscard'))) {
      return;
    }

    setRefreshingProject(true);
    setSaveError(null);
    setSaveConflict(null);
    setSaveSuccess(false);
    try {
      await onRefreshProject();
    } catch (err: any) {
      setSaveError(err?.response?.data?.detail || err?.message || t('fileViewer.refreshFailed'));
    } finally {
      setRefreshingProject(false);
    }
  }, [hasUnsavedChanges, onRefreshProject, refreshingProject, t]);

  useGlobalHotkey({ key: 's', onTrigger: handleSave });
  useGlobalHotkey({ key: 'k', onTrigger: inlineRewrite.handleToggleInlineRewrite });

  useEffect(() => {
    const handler = (rawEvent: Event) => {
      const event = rawEvent as CustomEvent<{ filePath?: string; line?: number }>;
      const filePath = typeof event.detail?.filePath === 'string' ? normalizeProjectPath(event.detail.filePath) : '';
      const rawLine = event.detail?.line;
      const line = typeof rawLine === 'number' ? rawLine : Number(rawLine);
      if (!filePath || !Number.isFinite(line) || line < 1) {
        return;
      }

      pendingJumpRef.current = { filePath, line: Math.floor(line) };
      if (content && normalizeProjectPath(content.path) === filePath) {
        window.setTimeout(() => jumpToLine(Math.floor(line)), 0);
      }
    };

    window.addEventListener('project-open-line', handler as EventListener);
    return () => window.removeEventListener('project-open-line', handler as EventListener);
  }, [content, jumpToLine]);

  useEffect(() => {
    if (!content || !pendingJumpRef.current) {
      return;
    }
    const pending = pendingJumpRef.current;
    if (normalizeProjectPath(content.path) !== pending.filePath) {
      return;
    }
    const timer = window.setTimeout(() => {
      jumpToLine(pending.line);
      pendingJumpRef.current = null;
    }, 0);
    return () => window.clearTimeout(timer);
  }, [content, jumpToLine]);

  // Detect dark mode from system preference (Tailwind defaults to media strategy)
  const [isDarkMode, setIsDarkMode] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return false;
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (event: MediaQueryListEvent) => {
      setIsDarkMode(event.matches);
    };

    setIsDarkMode(media.matches);

    if (media.addEventListener) {
      media.addEventListener('change', handleChange);
      return () => media.removeEventListener('change', handleChange);
    }

    media.addListener(handleChange);
    return () => media.removeListener(handleChange);
  }, []);

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

  // Ensure editor stretches to the available height
  const fullHeightTheme = useMemo(() => EditorView.theme({
    '&': { height: '100%' },
    '.cm-scroller': { height: '100%' },
    '.cm-content': { minHeight: '100%' }
  }), []);

  // Search extension (memoized to prevent re-creation)
  const searchExtension = useMemo(() => search({ top: true }), []);

  // Line wrapping extension (memoized)
  const lineWrappingExtension = useMemo(() => EditorView.lineWrapping, []);

  // Callback for when editor is created
  const onEditorCreate = useCallback((view: EditorView) => {
    editorViewRef.current = view;
    updateUndoRedoState();

    // Notify parent immediately when editor is ready
    if (onEditorReady) {
      onEditorReady({ insertContent: insertContentAtCursor });
    }
  }, [updateUndoRedoState, onEditorReady, insertContentAtCursor]);

  // Get language extension (memoized to prevent re-creation)
  const filePath = content?.path ?? '';
  const isMarkdownFile = useMemo(() => isMarkdownFilePath(filePath), [filePath]);
  const showMarkdownPreview = isMarkdownFile && markdownViewMode === 'preview';
  const language = useMemo(() => getLanguageExtension(filePath), [filePath]);

  // Build extensions array with conditional features (memoized to prevent re-creation)
  const extensions = useMemo(() => [
    language,
    lineWrapping && lineWrappingExtension,
    fontSizeTheme,
    fullHeightTheme,
    cursorPositionExtension,
    updateListener,
    searchExtension,
  ].filter(Boolean), [language, lineWrapping, lineWrappingExtension, fontSizeTheme, fullHeightTheme, cursorPositionExtension, updateListener, searchExtension]);

  const insertToChatTitle = isInsertingToChat
    ? 'Inserting to chat...'
    : 'Insert selection or file to chat';
  const refreshTitle = refreshingProject ? t('fileViewer.refreshing') : t('fileViewer.refresh');
  const inlineRewriteTitle = t('inlineRewrite.button');
  const sendToAgentTitle = t('workspace.agent.sendFileContextTitle');

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-gray-500 dark:text-gray-400">{t('fileViewer.loading')}</div>
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
      <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 overflow-hidden min-w-0">
        <FileViewerBreadcrumbBar
          projectName={projectName}
          fileTreeOpen={fileTreeOpen}
          onToggleFileTree={onToggleFileTree}
          refreshTitle={refreshTitle}
          refreshDisabled={refreshingProject || !onRefreshProject}
          refreshingProject={refreshingProject}
          onRefreshProject={handleRefreshProject}
          toggleTreeTitle={fileTreeOpen ? t('fileViewer.hideTree') : t('fileViewer.showTree')}
        />
        <div className="flex-1 flex flex-col items-center justify-center">
          <p className="text-gray-500 dark:text-gray-400 mb-2">{t('fileViewer.emptyState')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-white dark:bg-gray-900 min-w-0">
      <FileViewerBreadcrumbBar
        projectName={projectName}
        filePath={content.path}
        fileTreeOpen={fileTreeOpen}
        onToggleFileTree={onToggleFileTree}
        refreshTitle={refreshTitle}
        refreshDisabled={refreshingProject || !onRefreshProject}
        refreshingProject={refreshingProject}
        onRefreshProject={handleRefreshProject}
        toggleTreeTitle={fileTreeOpen ? t('fileViewer.hideTree') : t('fileViewer.showTree')}
      />
      <FileViewerEditorContent
        notice={notice}
        onDismissNotice={clearNotice}
        content={content}
        hasUnsavedChanges={hasUnsavedChanges}
        saving={saving}
        saveSuccess={saveSuccess}
        saveError={saveError}
        saveConflictState={saveConflict ? (saveConflict.remoteLoaded ? 'remoteLoaded' : 'detected') : 'none'}
        conflictBusy={conflictBusy}
        onLoadLatestAfterConflict={saveConflict ? handleLoadLatestAfterConflict : undefined}
        onRestoreConflictDraft={saveConflict?.remoteLoaded ? handleRestoreConflictDraft : undefined}
        onCopyConflictDraft={saveConflict ? handleCopyConflictDraft : undefined}
        onSave={handleSave}
        onCancel={handleCancel}
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
        isMarkdownFile={isMarkdownFile}
        markdownViewMode={markdownViewMode}
        onSetMarkdownViewMode={setMarkdownViewMode}
        autoSaveBeforeAgentSend={autoSaveBeforeAgentSend}
        onToggleAutoSaveBeforeAgentSend={setAutoSaveBeforeAgentSend}
        cursorPosition={cursorPosition}
        fileInfo={{ encoding: content.encoding, mimeType: content.mime_type, size: formatFileSize(content.size) }}
        chatSidebarOpen={chatSidebarOpen}
        onToggleChatSidebar={onToggleChatSidebar}
        onInsertToChat={handleInsertToChat}
        insertToChatDisabled={isInsertingToChat}
        insertToChatTitle={insertToChatTitle}
        onSendToAgent={handleSendToAgent}
        sendToAgentDisabled={false}
        sendToAgentTitle={sendToAgentTitle}
        onInlineRewrite={inlineRewrite.handleToggleInlineRewrite}
        inlineRewriteDisabled={inlineRewrite.inlineRewriteStreaming}
        inlineRewriteTitle={inlineRewriteTitle}
        onProjectWorkflow={inlineRewrite.handleOpenProjectWorkflowWorkspace}
        projectWorkflowDisabled={inlineRewrite.inlineRewriteStreaming}
        projectWorkflowTitle={t('projectWorkflow.shortcutButton')}
        projectId={projectId}
        inlineRewriteOpen={inlineRewrite.inlineRewriteOpen}
        inlineRewriteStreaming={inlineRewrite.inlineRewriteStreaming}
        inlineRewriteSourceText={inlineRewrite.inlineRewriteSourceText}
        inlineRewritePreview={inlineRewrite.inlineRewritePreview}
        inlineRewriteError={inlineRewrite.inlineRewriteError}
        rewriteWorkflowOptions={inlineRewrite.rewriteWorkflowOptions}
        selectedWorkflowId={inlineRewrite.selectedWorkflowId}
        inlineRewriteWorkflowsLoading={inlineRewrite.inlineRewriteWorkflowsLoading}
        inlineRewriteWorkflowInputs={inlineRewrite.inlineRewriteWorkflowInputs}
        inlineRewriteWorkflowNodeIds={inlineRewrite.inlineRewriteWorkflowNodeIds}
        inlineRewriteInputs={inlineRewrite.inlineRewriteInputs}
        favorites={inlineRewrite.favorites}
        recents={inlineRewrite.recents}
        inlineRewriteRecommendationContext={inlineRewrite.inlineRewriteRecommendationContext}
        onInlineRewriteWorkflowChange={inlineRewrite.handleInlineRewriteWorkflowChange}
        onToggleInlineRewriteFavorite={inlineRewrite.toggleFavorite}
        onInlineRewriteInputChange={inlineRewrite.handleInlineRewriteInputChange}
        onStartInlineRewrite={() => void inlineRewrite.handleStartInlineRewrite()}
        onStopInlineRewrite={inlineRewrite.handleStopInlineRewrite}
        showInlineRewriteNoSelectionPrompt={inlineRewrite.inlineRewriteNoSelectionPromptOpen}
        onRunInlineRewriteEmpty={inlineRewrite.handleNoSelectionRunEmpty}
        onRunInlineRewriteFullFile={inlineRewrite.handleNoSelectionRunFullFile}
        onCancelInlineRewriteNoSelection={inlineRewrite.handleNoSelectionRunCancel}
        onAcceptInlineRewrite={inlineRewrite.handleAcceptInlineRewrite}
        onCloseInlineRewrite={inlineRewrite.handleCloseInlineRewrite}
        onOpenWorkflowsPage={inlineRewrite.handleOpenWorkflowsPage}
        showMarkdownPreview={showMarkdownPreview}
        value={value}
        isDarkMode={isDarkMode}
        extensions={extensions}
        onEditorCreate={onEditorCreate}
        onEditorChange={setValue}
        prepareMarkdownForPreview={prepareMarkdownForPreview}
      />
    </div>
  );
};
