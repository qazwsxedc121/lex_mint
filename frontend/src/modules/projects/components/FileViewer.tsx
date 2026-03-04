/**
 * FileViewer - File content editor with CodeMirror
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import CodeMirror from '@uiw/react-codemirror';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { html } from '@codemirror/lang-html';
import { css } from '@codemirror/lang-css';
import { json } from '@codemirror/lang-json';
import { markdown } from '@codemirror/lang-markdown';
import { EditorView } from '@codemirror/view';
import { undo, redo, undoDepth, redoDepth } from '@codemirror/commands';
import { openSearchPanel, search } from '@codemirror/search';
import { ChevronDoubleLeftIcon, ChevronDoubleRightIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import type { FileContent } from '../../../types/project';
import type { Workflow, WorkflowInputDef } from '../../../types/workflow';
import { Breadcrumb } from './Breadcrumb';
import { listWorkflows, readFile, runWorkflowStream, writeFile } from '../../../services/api';
import { EditorToolbar } from './EditorToolbar';
import { useChatComposer, useChatServices } from '../../../shared/chat';
import { InlineRewritePanel } from './InlineRewritePanel';
import { ProjectWorkflowPanel } from './ProjectWorkflowPanel';
import { useWorkflowLauncherStorage } from '../../../shared/workflow-launcher/storage';
import type { LauncherRecommendationContext } from '../../../shared/workflow-launcher/types';

const CHAT_CONTEXT_MAX_CHARS = 6000;
const INLINE_REWRITE_CONTEXT_CHARS = 1200;
const AGENT_AUTO_SAVE_BEFORE_SEND_KEY = 'project-agent-auto-save-before-send';
const THINK_BLOCK_REGEX = /<think>[\s\S]*?<\/think>/g;
const DEFAULT_INLINE_REWRITE_WORKFLOW_ID = 'wf_inline_rewrite_default';
const PRIMARY_REWRITE_INPUT_KEYS = new Set(['input', 'text', 'selected_text']);
const AUTO_SLICE_KEY_PATTERN = /^(head|tail)_(line|char|percent)_(\d+)$/i;
const LEGACY_AUTO_REWRITE_INPUT_KEYS = new Set([
  ...PRIMARY_REWRITE_INPUT_KEYS,
  'context_before',
  'context_after',
  'file_path',
  'language',
  'project_id',
  'session_id',
  'selection_start',
  'selection_end',
  'source_mode',
]);

const normalizeAutoKey = (key: string): string => key.replace(/^_+/, '').toLowerCase();
const isSelectionInputKey = (key: string): boolean => PRIMARY_REWRITE_INPUT_KEYS.has(normalizeAutoKey(key));
const isSliceAutoKey = (key: string): boolean => {
  const normalizedKey = normalizeAutoKey(key);
  return normalizedKey === 'full_text' || AUTO_SLICE_KEY_PATTERN.test(normalizedKey);
};
const isAutoRewriteInputKey = (key: string): boolean =>
  key.startsWith('_') || LEGACY_AUTO_REWRITE_INPUT_KEYS.has(key.toLowerCase()) || isSliceAutoKey(key);

type RewriteSourceMode = 'selection' | 'empty' | 'full_file';

const assignAutoValueWithAliases = (target: Record<string, unknown>, key: string, value: unknown) => {
  const normalizedKey = normalizeAutoKey(key);
  target[normalizedKey] = value;
  target[`_${normalizedKey}`] = value;
};

const buildSlicedAutoValue = (fullText: string, key: string): string | null => {
  const normalizedKey = normalizeAutoKey(key);
  if (normalizedKey === 'full_text') {
    return fullText;
  }

  const match = normalizedKey.match(AUTO_SLICE_KEY_PATTERN);
  if (!match) {
    return null;
  }

  const [, directionRaw, unitRaw, amountRaw] = match;
  const direction = directionRaw.toLowerCase() as 'head' | 'tail';
  const unit = unitRaw.toLowerCase() as 'line' | 'char' | 'percent';
  const parsedAmount = Number(amountRaw);
  if (!Number.isFinite(parsedAmount) || parsedAmount < 0) {
    return null;
  }

  if (unit === 'line') {
    const lines = fullText.split('\n');
    const take = Math.max(0, Math.floor(parsedAmount));
    const sliced = direction === 'head'
      ? lines.slice(0, take)
      : lines.slice(Math.max(lines.length - take, 0));
    return sliced.join('\n');
  }

  if (unit === 'char') {
    const take = Math.max(0, Math.floor(parsedAmount));
    if (direction === 'head') {
      return fullText.slice(0, take);
    }
    return fullText.slice(Math.max(fullText.length - take, 0));
  }

  const boundedPercent = Math.min(100, Math.max(0, Math.floor(parsedAmount)));
  const take = Math.ceil(fullText.length * (boundedPercent / 100));
  if (direction === 'head') {
    return fullText.slice(0, take);
  }
  return fullText.slice(Math.max(fullText.length - take, 0));
};

interface RewriteSelectionSnapshot {
  from: number;
  to: number;
  sourceMode: RewriteSourceMode;
  selectedText: string;
  contextBefore: string;
  contextAfter: string;
  filePath: string;
  language: string;
}

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
  const [inlineRewriteOpen, setInlineRewriteOpen] = useState(false);
  const [inlineRewriteStreaming, setInlineRewriteStreaming] = useState(false);
  const [inlineRewriteError, setInlineRewriteError] = useState<string | null>(null);
  const [inlineRewriteNoSelectionPromptOpen, setInlineRewriteNoSelectionPromptOpen] = useState(false);
  const [inlineRewriteInputs, setInlineRewriteInputs] = useState<Record<string, unknown>>({});
  const [inlineRewriteSourceText, setInlineRewriteSourceText] = useState('');
  const [inlineRewritePreview, setInlineRewritePreview] = useState('');
  const [inlineRewriteWorkflowId, setInlineRewriteWorkflowId] = useState(DEFAULT_INLINE_REWRITE_WORKFLOW_ID);
  const [inlineRewriteWorkflows, setInlineRewriteWorkflows] = useState<Workflow[]>([]);
  const [inlineRewriteWorkflowsLoading, setInlineRewriteWorkflowsLoading] = useState(false);
  const [projectWorkflowOpen, setProjectWorkflowOpen] = useState(false);
  const [projectWorkflowRunning, setProjectWorkflowRunning] = useState(false);
  const [projectWorkflowError, setProjectWorkflowError] = useState<string | null>(null);
  const [projectWorkflowInputs, setProjectWorkflowInputs] = useState<Record<string, unknown>>({});
  const [projectWorkflowOutput, setProjectWorkflowOutput] = useState('');
  const [projectWorkflowId, setProjectWorkflowId] = useState('');
  const [projectWorkflowArtifactPath, setProjectWorkflowArtifactPath] = useState('');
  const [projectWorkflowWriteMode, setProjectWorkflowWriteMode] = useState<'none' | 'create' | 'overwrite'>('overwrite');
  const [autoSaveBeforeAgentSend, setAutoSaveBeforeAgentSend] = useState<boolean>(() => {
    return localStorage.getItem(AGENT_AUTO_SAVE_BEFORE_SEND_KEY) === 'true';
  });

  const { currentSessionId, createSession, createTemporarySession, navigation } = useChatServices();
  const chatComposer = useChatComposer();
  const { favoritesSet: launcherFavorites, recents: launcherRecents, toggleFavorite: toggleLauncherFavorite, addRecent: addLauncherRecent } = useWorkflowLauncherStorage();

  // Editor view reference
  const editorViewRef = useRef<EditorView | null>(null);
  const inlineRewriteAbortRef = useRef<AbortController | null>(null);
  const projectWorkflowAbortRef = useRef<AbortController | null>(null);
  const rewriteSelectionRef = useRef<RewriteSelectionSnapshot | null>(null);
  const pendingJumpRef = useRef<{ filePath: string; line: number } | null>(null);

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

  useEffect(() => {
    localStorage.setItem(AGENT_AUTO_SAVE_BEFORE_SEND_KEY, autoSaveBeforeAgentSend ? 'true' : 'false');
  }, [autoSaveBeforeAgentSend]);

  // Sync content when file changes
  useEffect(() => {
    if (content) {
      setValue(content.content);
      setOriginalContent(content.content);
      setOriginalHash(content.content_hash || null);
      setSaveError(null);
      setSaveConflict(null);
      setConflictBusy(false);
      setSaveSuccess(false);
      setInlineRewriteOpen(false);
      setInlineRewriteStreaming(false);
      setInlineRewriteError(null);
      setInlineRewriteNoSelectionPromptOpen(false);
      setInlineRewriteInputs({});
      setInlineRewriteSourceText('');
      setInlineRewritePreview('');
      rewriteSelectionRef.current = null;
    }
  }, [content]);

  useEffect(() => {
    setProjectWorkflowOpen(false);
    setProjectWorkflowRunning(false);
    setProjectWorkflowError(null);
    setProjectWorkflowInputs({});
    setProjectWorkflowOutput('');
    setProjectWorkflowArtifactPath('');
    projectWorkflowAbortRef.current?.abort();
    projectWorkflowAbortRef.current = null;
  }, [projectId]);

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
      alert('Failed to create chat session. Please try again.');
      return null;
    }
  }, [currentSessionId, createSession, navigation]);

  const ensureInlineRewriteSession = useCallback(async () => {
    if (currentSessionId) {
      return currentSessionId;
    }

    try {
      const newSessionId = await createTemporarySession();
      navigation?.navigateToSession(newSessionId);
      return newSessionId;
    } catch (err) {
      console.error('Failed to create temporary project session for inline rewrite:', err);
      setInlineRewriteError(t('inlineRewrite.createSessionFailed'));
      return null;
    }
  }, [currentSessionId, createTemporarySession, navigation, t]);

  const getInlineRewriteSelectionSnapshot = useCallback((): RewriteSelectionSnapshot | null => {
    if (!content || !editorViewRef.current) {
      return null;
    }

    const view = editorViewRef.current;
    const selection = view.state.selection.main;
    if (selection.empty) {
      return null;
    }

    const selectedText = view.state.doc.sliceString(selection.from, selection.to);
    if (!selectedText.trim()) {
      return null;
    }

    const contextBefore = view.state.doc.sliceString(
      Math.max(0, selection.from - INLINE_REWRITE_CONTEXT_CHARS),
      selection.from
    );
    const contextAfter = view.state.doc.sliceString(
      selection.to,
      Math.min(view.state.doc.length, selection.to + INLINE_REWRITE_CONTEXT_CHARS)
    );

    return {
      from: selection.from,
      to: selection.to,
      sourceMode: 'selection',
      selectedText,
      contextBefore,
      contextAfter,
      filePath: content.path,
      language: getLanguageTag(content.path),
    };
  }, [content]);

  const getInlineRewriteSnapshotForNoSelection = useCallback(
    (sourceMode: Exclude<RewriteSourceMode, 'selection'>): RewriteSelectionSnapshot | null => {
      if (!content || !editorViewRef.current) {
        return null;
      }

      const view = editorViewRef.current;
      const docText = view.state.doc.toString();
      const docLength = view.state.doc.length;
      const cursor = view.state.selection.main.head;

      if (sourceMode === 'full_file') {
        return {
          from: 0,
          to: docLength,
          sourceMode,
          selectedText: docText,
          contextBefore: '',
          contextAfter: '',
          filePath: content.path,
          language: getLanguageTag(content.path),
        };
      }

      const contextBefore = view.state.doc.sliceString(
        Math.max(0, cursor - INLINE_REWRITE_CONTEXT_CHARS),
        cursor
      );
      const contextAfter = view.state.doc.sliceString(
        cursor,
        Math.min(view.state.doc.length, cursor + INLINE_REWRITE_CONTEXT_CHARS)
      );
      return {
        from: cursor,
        to: cursor,
        sourceMode,
        selectedText: '',
        contextBefore,
        contextAfter,
        filePath: content.path,
        language: getLanguageTag(content.path),
      };
    },
    [content]
  );

  const rewriteWorkflowOptions = useMemo(
    () =>
      inlineRewriteWorkflows.filter((workflow) => workflow.enabled && workflow.scenario === 'editor_rewrite'),
    [inlineRewriteWorkflows]
  );
  const activeRewriteWorkflow = useMemo(() => {
    if (rewriteWorkflowOptions.length === 0) {
      return null;
    }
    return (
      rewriteWorkflowOptions.find((workflow) => workflow.id === inlineRewriteWorkflowId) ||
      rewriteWorkflowOptions[0]
    );
  }, [inlineRewriteWorkflowId, rewriteWorkflowOptions]);
  const inlineRewriteWorkflowInputs = useMemo(() => {
    if (!activeRewriteWorkflow) {
      return [] as WorkflowInputDef[];
    }
    return activeRewriteWorkflow.input_schema.filter(
      (inputDef) => !isAutoRewriteInputKey(inputDef.key)
    );
  }, [activeRewriteWorkflow]);
  const inlineRewriteRecommendationContext = useMemo<LauncherRecommendationContext>(
    () => ({
      module: 'projects',
      requiredScenario: 'editor_rewrite',
      filePath: content?.path,
      hasSelection: Boolean(inlineRewriteSourceText.trim()),
    }),
    [content?.path, inlineRewriteSourceText]
  );
  const projectPipelineWorkflowOptions = useMemo(
    () =>
      inlineRewriteWorkflows.filter(
        (workflow) => workflow.enabled && workflow.scenario === 'project_pipeline'
      ),
    [inlineRewriteWorkflows]
  );
  const activeProjectWorkflow = useMemo(() => {
    if (projectPipelineWorkflowOptions.length === 0) {
      return null;
    }
    return (
      projectPipelineWorkflowOptions.find((workflow) => workflow.id === projectWorkflowId) ||
      projectPipelineWorkflowOptions[0]
    );
  }, [projectPipelineWorkflowOptions, projectWorkflowId]);
  const projectWorkflowInputDefs = useMemo(
    () => activeProjectWorkflow?.input_schema || ([] as WorkflowInputDef[]),
    [activeProjectWorkflow]
  );
  const projectWorkflowRecommendationContext = useMemo<LauncherRecommendationContext>(
    () => ({
      module: 'projects',
      requiredScenario: 'project_pipeline',
      filePath: content?.path,
      hasSelection: Boolean(inlineRewriteSourceText.trim()),
    }),
    [content?.path, inlineRewriteSourceText]
  );

  const buildInlineRewriteDefaultInputs = useCallback((workflow: Workflow): Record<string, unknown> => {
    const defaults: Record<string, unknown> = {};
    for (const inputDef of workflow.input_schema) {
      if (isAutoRewriteInputKey(inputDef.key)) {
        continue;
      }
      if (inputDef.default !== undefined) {
        defaults[inputDef.key] = inputDef.default;
      }
    }
    return defaults;
  }, []);
  const buildProjectWorkflowDefaultInputs = useCallback((workflow: Workflow): Record<string, unknown> => {
    const defaults: Record<string, unknown> = {};
    for (const inputDef of workflow.input_schema) {
      if (inputDef.default !== undefined) {
        defaults[inputDef.key] = inputDef.default;
      }
    }
    return defaults;
  }, []);

  const buildInlineRewriteAutoInputs = useCallback(
    (
      workflow: Workflow,
      snapshot: RewriteSelectionSnapshot,
      fullText: string,
      sessionId?: string | null
    ): Record<string, unknown> => {
      const autoValues: Record<string, unknown> = {};

      assignAutoValueWithAliases(autoValues, 'input', snapshot.selectedText);
      assignAutoValueWithAliases(autoValues, 'text', snapshot.selectedText);
      assignAutoValueWithAliases(autoValues, 'selected_text', snapshot.selectedText);
      assignAutoValueWithAliases(autoValues, 'context_before', snapshot.contextBefore);
      assignAutoValueWithAliases(autoValues, 'context_after', snapshot.contextAfter);
      assignAutoValueWithAliases(autoValues, 'file_path', snapshot.filePath);
      assignAutoValueWithAliases(autoValues, 'language', snapshot.language);
      assignAutoValueWithAliases(autoValues, 'selection_start', snapshot.from);
      assignAutoValueWithAliases(autoValues, 'selection_end', snapshot.to);
      assignAutoValueWithAliases(autoValues, 'source_mode', snapshot.sourceMode);
      assignAutoValueWithAliases(autoValues, 'full_text', fullText);
      if (projectId) {
        assignAutoValueWithAliases(autoValues, 'project_id', projectId);
      }
      if (sessionId) {
        assignAutoValueWithAliases(autoValues, 'session_id', sessionId);
      }

      for (const inputDef of workflow.input_schema) {
        if (!isSliceAutoKey(inputDef.key)) {
          continue;
        }
        const slicedValue = buildSlicedAutoValue(fullText, inputDef.key);
        if (slicedValue === null) {
          continue;
        }
        assignAutoValueWithAliases(autoValues, inputDef.key, slicedValue);
      }

      return autoValues;
    },
    [projectId]
  );

  const ensureInlineRewriteWorkflowsLoaded = useCallback(async (): Promise<Workflow[]> => {
    if (inlineRewriteWorkflowsLoading) {
      return rewriteWorkflowOptions;
    }

    setInlineRewriteWorkflowsLoading(true);
    try {
      const workflows = await listWorkflows();
      const rewriteWorkflows = workflows.filter(
        (workflow) => workflow.enabled && workflow.scenario === 'editor_rewrite'
      );
      setInlineRewriteWorkflows(workflows);

      if (rewriteWorkflows.length === 0) {
        setInlineRewriteWorkflowId('');
        setInlineRewriteError((previous) => previous || t('inlineRewrite.noWorkflows'));
        return [];
      }

      setInlineRewriteWorkflowId((previous) => {
        if (previous && rewriteWorkflows.some((workflow) => workflow.id === previous)) {
          return previous;
        }
        const defaultWorkflow = rewriteWorkflows.find(
          (workflow) => workflow.id === DEFAULT_INLINE_REWRITE_WORKFLOW_ID
        );
        return defaultWorkflow?.id || rewriteWorkflows[0].id;
      });
      return rewriteWorkflows;
    } catch (err) {
      console.error('Failed to load inline rewrite workflows:', err);
      setInlineRewriteError(t('inlineRewrite.loadWorkflowsFailed'));
      return [];
    } finally {
      setInlineRewriteWorkflowsLoading(false);
    }
  }, [inlineRewriteWorkflowsLoading, rewriteWorkflowOptions, t]);
  const ensureProjectPipelineWorkflowsLoaded = useCallback(async (): Promise<Workflow[]> => {
    if (inlineRewriteWorkflowsLoading) {
      return projectPipelineWorkflowOptions;
    }

    setInlineRewriteWorkflowsLoading(true);
    try {
      const workflows = await listWorkflows();
      const pipelineWorkflows = workflows.filter(
        (workflow) => workflow.enabled && workflow.scenario === 'project_pipeline'
      );
      setInlineRewriteWorkflows(workflows);

      if (pipelineWorkflows.length === 0) {
        setProjectWorkflowId('');
        setProjectWorkflowError((previous) => previous || t('projectWorkflow.noWorkflows'));
        return [];
      }

      setProjectWorkflowId((previous) => {
        if (previous && pipelineWorkflows.some((workflow) => workflow.id === previous)) {
          return previous;
        }
        return pipelineWorkflows[0].id;
      });
      return pipelineWorkflows;
    } catch (err) {
      console.error('Failed to load project pipeline workflows:', err);
      setProjectWorkflowError(t('projectWorkflow.loadWorkflowsFailed'));
      return [];
    } finally {
      setInlineRewriteWorkflowsLoading(false);
    }
  }, [inlineRewriteWorkflowsLoading, projectPipelineWorkflowOptions, t]);

  useEffect(() => {
    if (!activeRewriteWorkflow) {
      setInlineRewriteInputs({});
      return;
    }
    setInlineRewriteInputs(buildInlineRewriteDefaultInputs(activeRewriteWorkflow));
  }, [activeRewriteWorkflow, buildInlineRewriteDefaultInputs]);
  useEffect(() => {
    if (!activeProjectWorkflow) {
      setProjectWorkflowInputs({});
      return;
    }
    setProjectWorkflowInputs(buildProjectWorkflowDefaultInputs(activeProjectWorkflow));
  }, [activeProjectWorkflow, buildProjectWorkflowDefaultInputs]);

  const handleInlineRewriteWorkflowChange = useCallback((workflowId: string) => {
    if (inlineRewriteStreaming) {
      return;
    }
    setInlineRewriteWorkflowId(workflowId);
    setInlineRewriteError(null);
    setInlineRewritePreview('');
  }, [inlineRewriteStreaming]);

  const handleInlineRewriteInputChange = useCallback((key: string, value: unknown) => {
    setInlineRewriteInputs((previous) => {
      const next = { ...previous };
      if (value === undefined) {
        delete next[key];
      } else {
        next[key] = value;
      }
      return next;
    });
  }, []);
  const handleProjectWorkflowChange = useCallback((workflowId: string) => {
    if (projectWorkflowRunning) {
      return;
    }
    setProjectWorkflowId(workflowId);
    setProjectWorkflowError(null);
    setProjectWorkflowOutput('');
  }, [projectWorkflowRunning]);
  const handleProjectWorkflowInputChange = useCallback((key: string, value: unknown) => {
    setProjectWorkflowInputs((previous) => {
      const next = { ...previous };
      if (value === undefined) {
        delete next[key];
      } else {
        next[key] = value;
      }
      return next;
    });
  }, []);

  const workflowRequiresSelection = useCallback((workflow: Workflow): boolean => {
    return workflow.input_schema.some(
      (inputDef) => inputDef.required && isSelectionInputKey(inputDef.key)
    );
  }, []);

  const buildInlineRewriteRunInputs = useCallback(
    (
      workflow: Workflow,
      snapshot: RewriteSelectionSnapshot,
      fullText: string,
      sessionId?: string | null
    ): { inputs: Record<string, unknown>; error?: string } => {
      const autoInputs = buildInlineRewriteAutoInputs(workflow, snapshot, fullText, sessionId);
      const runInputs: Record<string, unknown> = { ...inlineRewriteInputs, ...autoInputs };

      for (const inputDef of workflow.input_schema) {
        let value = runInputs[inputDef.key];
        if (value === undefined && inputDef.default !== undefined) {
          value = inputDef.default;
        }

        if (value === undefined || value === null || (inputDef.type !== 'string' && value === '')) {
          if (inputDef.required) {
            return {
              inputs: runInputs,
              error: t('inlineRewrite.missingRequiredInput', { key: inputDef.key }),
            };
          }
          continue;
        }

        if (inputDef.type === 'string') {
          runInputs[inputDef.key] = typeof value === 'string' ? value : String(value);
          continue;
        }

        if (inputDef.type === 'number') {
          if (typeof value !== 'number' || Number.isNaN(value)) {
            return {
              inputs: runInputs,
              error: t('inlineRewrite.invalidNumberInput', { key: inputDef.key }),
            };
          }
          runInputs[inputDef.key] = value;
          continue;
        }

        if (inputDef.type === 'boolean') {
          if (typeof value !== 'boolean') {
            return {
              inputs: runInputs,
              error: t('inlineRewrite.invalidBooleanInput', { key: inputDef.key }),
            };
          }
          runInputs[inputDef.key] = value;
        }
      }

      return { inputs: runInputs };
    },
    [buildInlineRewriteAutoInputs, inlineRewriteInputs, t]
  );
  const buildProjectWorkflowRunInputs = useCallback(
    (workflow: Workflow): { inputs: Record<string, unknown>; error?: string } => {
      const runInputs: Record<string, unknown> = { ...projectWorkflowInputs };

      for (const inputDef of workflow.input_schema) {
        let value = runInputs[inputDef.key];
        if (value === undefined && inputDef.default !== undefined) {
          value = inputDef.default;
        }

        if (value === undefined || value === null || (inputDef.type !== 'string' && value === '')) {
          if (inputDef.required) {
            return {
              inputs: runInputs,
              error: t('projectWorkflow.missingRequiredInput', { key: inputDef.key }),
            };
          }
          continue;
        }

        if (inputDef.type === 'string') {
          runInputs[inputDef.key] = typeof value === 'string' ? value : String(value);
          continue;
        }

        if (inputDef.type === 'number') {
          if (typeof value !== 'number' || Number.isNaN(value)) {
            return {
              inputs: runInputs,
              error: t('projectWorkflow.invalidNumberInput', { key: inputDef.key }),
            };
          }
          runInputs[inputDef.key] = value;
          continue;
        }

        if (inputDef.type === 'boolean') {
          if (typeof value !== 'boolean') {
            return {
              inputs: runInputs,
              error: t('projectWorkflow.invalidBooleanInput', { key: inputDef.key }),
            };
          }
          runInputs[inputDef.key] = value;
        }
      }

      return { inputs: runInputs };
    },
    [projectWorkflowInputs, t]
  );

  const handleOpenInlineRewrite = useCallback(() => {
    void ensureInlineRewriteWorkflowsLoaded();
    const snapshot = getInlineRewriteSelectionSnapshot();
    setProjectWorkflowOpen(false);
    setInlineRewriteOpen(true);
    setInlineRewriteError(null);
    setInlineRewriteNoSelectionPromptOpen(false);

    if (activeRewriteWorkflow) {
      const defaults = buildInlineRewriteDefaultInputs(activeRewriteWorkflow);
      setInlineRewriteInputs(defaults);
    }

    setInlineRewriteSourceText(snapshot?.selectedText || '');
    setInlineRewritePreview('');
  }, [
    ensureInlineRewriteWorkflowsLoaded,
    getInlineRewriteSelectionSnapshot,
    activeRewriteWorkflow,
    buildInlineRewriteDefaultInputs,
  ]);
  const handleOpenProjectWorkflow = useCallback(() => {
    void ensureProjectPipelineWorkflowsLoaded();
    setInlineRewriteOpen(false);
    setProjectWorkflowOpen(true);
    setProjectWorkflowError(null);
    setProjectWorkflowOutput('');
    if (activeProjectWorkflow) {
      setProjectWorkflowInputs(buildProjectWorkflowDefaultInputs(activeProjectWorkflow));
    }
  }, [
    activeProjectWorkflow,
    buildProjectWorkflowDefaultInputs,
    ensureProjectPipelineWorkflowsLoaded,
  ]);

  const handleStopInlineRewrite = useCallback(() => {
    inlineRewriteAbortRef.current?.abort();
    inlineRewriteAbortRef.current = null;
    setInlineRewriteStreaming(false);
  }, []);
  const handleStopProjectWorkflow = useCallback(() => {
    projectWorkflowAbortRef.current?.abort();
    projectWorkflowAbortRef.current = null;
    setProjectWorkflowRunning(false);
  }, []);

  const handleCloseInlineRewrite = useCallback(() => {
    handleStopInlineRewrite();
    setInlineRewriteOpen(false);
    setInlineRewriteError(null);
    setInlineRewriteNoSelectionPromptOpen(false);
    setInlineRewritePreview('');
    rewriteSelectionRef.current = null;
  }, [handleStopInlineRewrite]);
  const handleCloseProjectWorkflow = useCallback(() => {
    handleStopProjectWorkflow();
    setProjectWorkflowOpen(false);
    setProjectWorkflowError(null);
    setProjectWorkflowOutput('');
  }, [handleStopProjectWorkflow]);

  const handleToggleInlineRewrite = useCallback(() => {
    if (inlineRewriteOpen) {
      handleCloseInlineRewrite();
      return;
    }
    handleOpenInlineRewrite();
  }, [inlineRewriteOpen, handleCloseInlineRewrite, handleOpenInlineRewrite]);
  const handleToggleProjectWorkflow = useCallback(() => {
    if (projectWorkflowOpen) {
      handleCloseProjectWorkflow();
      return;
    }
    handleOpenProjectWorkflow();
  }, [projectWorkflowOpen, handleCloseProjectWorkflow, handleOpenProjectWorkflow]);

  const handleOpenWorkflowsPage = useCallback(() => {
    navigate('/workflows');
  }, [navigate]);
  const handleRunProjectWorkflow = useCallback(async () => {
    if (projectWorkflowRunning || !content) {
      return;
    }

    const availableWorkflows =
      projectPipelineWorkflowOptions.length > 0
        ? projectPipelineWorkflowOptions
        : await ensureProjectPipelineWorkflowsLoaded();
    if (availableWorkflows.length === 0) {
      setProjectWorkflowOpen(true);
      setProjectWorkflowError(t('projectWorkflow.noWorkflows'));
      return;
    }

    const workflowToRun =
      availableWorkflows.find((workflow) => workflow.id === projectWorkflowId) || availableWorkflows[0];
    if (!workflowToRun) {
      setProjectWorkflowOpen(true);
      setProjectWorkflowError(t('projectWorkflow.noWorkflows'));
      return;
    }

    const prepared = buildProjectWorkflowRunInputs(workflowToRun);
    if (prepared.error) {
      setProjectWorkflowError(prepared.error);
      return;
    }

    setProjectWorkflowRunning(true);
    setProjectWorkflowError(null);
    setProjectWorkflowOutput('');

    const normalizedArtifactPath = projectWorkflowArtifactPath.trim();
    try {
      await runWorkflowStream(
        workflowToRun.id,
        prepared.inputs,
        {
          onEvent: (event) => {
            if (event.event_type === 'workflow_artifact_written') {
              const writtenPath = event.payload.file_path;
              const written = event.payload.written === true;
              if (typeof writtenPath === 'string' && writtenPath.trim()) {
                setProjectWorkflowOutput((previous) => {
                  const prefix = previous ? `${previous}\n\n` : '';
                  return `${prefix}[artifact] ${writtenPath}`;
                });
                if (written) {
                  window.dispatchEvent(new CustomEvent('project-tree-updated', {
                    detail: { projectId, filePath: writtenPath },
                  }));
                }
              }
            }
          },
          onChunk: (chunk) => {
            setProjectWorkflowOutput((prev) => prev + chunk);
          },
          onComplete: () => {
            setProjectWorkflowRunning(false);
            addLauncherRecent(workflowToRun.id);
          },
          onError: (errorMessage) => {
            setProjectWorkflowRunning(false);
            setProjectWorkflowError(errorMessage);
          },
        },
        projectWorkflowAbortRef,
        {
          sessionId: currentSessionId || undefined,
          contextType: 'project',
          projectId,
          streamMode: 'default',
          artifactTargetPath: normalizedArtifactPath || undefined,
          writeMode: projectWorkflowWriteMode,
        }
      );
    } catch (err) {
      console.error('Project workflow request failed:', err);
      setProjectWorkflowError(err instanceof Error ? err.message : t('projectWorkflow.requestFailed'));
    } finally {
      setProjectWorkflowRunning(false);
    }
  }, [
    addLauncherRecent,
    buildProjectWorkflowRunInputs,
    content,
    currentSessionId,
    ensureProjectPipelineWorkflowsLoaded,
    projectId,
    projectPipelineWorkflowOptions,
    projectWorkflowArtifactPath,
    projectWorkflowId,
    projectWorkflowRunning,
    projectWorkflowWriteMode,
    t,
  ]);

  const handleStartInlineRewrite = useCallback(async (noSelectionMode: 'ask' | 'empty' | 'full_file' = 'ask') => {
    if (inlineRewriteStreaming || !content) {
      return;
    }

    const availableWorkflows =
      rewriteWorkflowOptions.length > 0
        ? rewriteWorkflowOptions
        : await ensureInlineRewriteWorkflowsLoaded();
    if (availableWorkflows.length === 0) {
      setInlineRewriteOpen(true);
      setInlineRewriteError(t('inlineRewrite.noWorkflows'));
      return;
    }
    const workflowToRun =
      availableWorkflows.find((workflow) => workflow.id === inlineRewriteWorkflowId) || availableWorkflows[0];
    if (!workflowToRun) {
      setInlineRewriteOpen(true);
      setInlineRewriteError(t('inlineRewrite.noWorkflows'));
      return;
    }

    let snapshot = getInlineRewriteSelectionSnapshot();
    if (!snapshot) {
      const requiresSelection = workflowRequiresSelection(workflowToRun);
      if (requiresSelection && noSelectionMode === 'ask') {
        setInlineRewriteNoSelectionPromptOpen(true);
        setInlineRewriteError(null);
        return;
      }
      const resolvedNoSelectionMode = noSelectionMode === 'full_file' ? 'full_file' : 'empty';
      snapshot = getInlineRewriteSnapshotForNoSelection(resolvedNoSelectionMode);
      if (!snapshot) {
        setInlineRewriteError(t('inlineRewrite.selectionMissing'));
        return;
      }
    }

    const sessionId = await ensureInlineRewriteSession();
    if (!sessionId) {
      return;
    }

    const currentFullText = editorViewRef.current?.state.doc.toString() ?? value;
    rewriteSelectionRef.current = snapshot;
    setInlineRewriteSourceText(snapshot.selectedText);
    setInlineRewritePreview('');
    setInlineRewriteError(null);
    setInlineRewriteNoSelectionPromptOpen(false);
    setInlineRewriteStreaming(true);

    const prepared = buildInlineRewriteRunInputs(workflowToRun, snapshot, currentFullText, sessionId);
    if (prepared.error) {
      setInlineRewriteStreaming(false);
      setInlineRewriteError(prepared.error);
      return;
    }

    try {
      await runWorkflowStream(
        workflowToRun.id,
        prepared.inputs,
        {
          onChunk: (chunk) => {
            setInlineRewritePreview((prev) => prev + chunk);
          },
          onComplete: () => {
            setInlineRewriteStreaming(false);
            addLauncherRecent(workflowToRun.id);
          },
          onError: (errorMessage) => {
            setInlineRewriteStreaming(false);
            setInlineRewriteError(errorMessage);
          },
        },
        inlineRewriteAbortRef,
        {
          sessionId,
          contextType: 'project',
          projectId,
          streamMode: 'editor_rewrite',
        }
      );
    } catch (err) {
      console.error('Inline rewrite request failed:', err);
      setInlineRewriteError(err instanceof Error ? err.message : t('inlineRewrite.requestFailed'));
    } finally {
      setInlineRewriteStreaming(false);
    }
  }, [
    inlineRewriteStreaming,
    content,
    rewriteWorkflowOptions,
    ensureInlineRewriteWorkflowsLoaded,
    inlineRewriteWorkflowId,
    getInlineRewriteSelectionSnapshot,
    workflowRequiresSelection,
    getInlineRewriteSnapshotForNoSelection,
    t,
    ensureInlineRewriteSession,
    value,
    buildInlineRewriteRunInputs,
    projectId,
    addLauncherRecent,
  ]);

  const handleNoSelectionRunEmpty = useCallback(() => {
    void handleStartInlineRewrite('empty');
  }, [handleStartInlineRewrite]);

  const handleNoSelectionRunFullFile = useCallback(() => {
    void handleStartInlineRewrite('full_file');
  }, [handleStartInlineRewrite]);

  const handleNoSelectionRunCancel = useCallback(() => {
    setInlineRewriteNoSelectionPromptOpen(false);
  }, []);

  const handleAcceptInlineRewrite = useCallback(() => {
    if (!editorViewRef.current) {
      return;
    }
    const selectionSnapshot = rewriteSelectionRef.current;
    if (!selectionSnapshot) {
      setInlineRewriteError(t('inlineRewrite.selectionMissing'));
      return;
    }

    const rewrittenText = inlineRewritePreview.replace(THINK_BLOCK_REGEX, '');
    if (!rewrittenText.trim()) {
      setInlineRewriteError(t('inlineRewrite.emptyRewriteResult'));
      return;
    }

    const view = editorViewRef.current;
    const currentSelectedText = view.state.doc.sliceString(selectionSnapshot.from, selectionSnapshot.to);
    if (currentSelectedText !== selectionSnapshot.selectedText) {
      setInlineRewriteError(t('inlineRewrite.selectionChanged'));
      return;
    }

    view.dispatch({
      changes: {
        from: selectionSnapshot.from,
        to: selectionSnapshot.to,
        insert: rewrittenText,
      },
      selection: {
        anchor: selectionSnapshot.from,
        head: selectionSnapshot.from + rewrittenText.length,
      },
    });
    view.focus();

    setInlineRewriteOpen(false);
    setInlineRewriteError(null);
    setInlineRewritePreview('');
    rewriteSelectionRef.current = null;
  }, [inlineRewritePreview, t]);

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
      alert('Failed to insert content into chat. Please try again.');
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
  ]);

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
  }, [handleSave]);

  // Ctrl/Cmd+K handler for toggling inline rewrite panel
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        handleToggleInlineRewrite();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleToggleInlineRewrite]);

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

  useEffect(() => {
    return () => {
      inlineRewriteAbortRef.current?.abort();
      inlineRewriteAbortRef.current = null;
      projectWorkflowAbortRef.current?.abort();
      projectWorkflowAbortRef.current = null;
    };
  }, []);

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

  const renderBreadcrumbBar = (filePath?: string) => (
    <div data-name="file-viewer-breadcrumb-bar" className="border-b border-gray-300 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800">
      <div data-name="file-viewer-breadcrumb-row" className="flex items-center gap-2 min-w-0">
        <button
          type="button"
          title={fileTreeOpen ? t('fileViewer.hideTree') : t('fileViewer.showTree')}
          aria-pressed={fileTreeOpen}
          onClick={onToggleFileTree}
          data-name="file-tree-toggle"
          className={`p-1.5 rounded ${
            fileTreeOpen
              ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
              : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
          }`}
        >
          {fileTreeOpen ? (
            <ChevronDoubleLeftIcon className="h-4 w-4" />
          ) : (
            <ChevronDoubleRightIcon className="h-4 w-4" />
          )}
        </button>
        <div className="min-w-0 flex-1">
          {filePath ? (
            <Breadcrumb projectName={projectName} filePath={filePath} />
          ) : (
            <div data-name="file-viewer-breadcrumb-placeholder" className="text-sm text-gray-600 dark:text-gray-400 font-medium">
              {projectName}
            </div>
          )}
        </div>
        <button
          type="button"
          title={refreshTitle}
          aria-label={refreshTitle}
          onClick={handleRefreshProject}
          disabled={refreshingProject || !onRefreshProject}
          data-name="project-refresh-button"
          className={`p-1.5 rounded ${
            refreshingProject || !onRefreshProject
              ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed opacity-60'
              : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
          }`}
        >
          <ArrowPathIcon className={`h-4 w-4 ${refreshingProject ? 'animate-spin' : ''}`} />
        </button>
      </div>
    </div>
  );

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
        {renderBreadcrumbBar()}
        <div className="flex-1 flex flex-col items-center justify-center">
          <p className="text-gray-500 dark:text-gray-400 mb-2">{t('fileViewer.emptyState')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 overflow-hidden min-w-0">
      {/* Breadcrumb */}
      {renderBreadcrumbBar(content.path)}

      {/* Toolbar */}
      <EditorToolbar
        onSave={handleSave}
        onCancel={handleCancel}
        hasUnsavedChanges={hasUnsavedChanges}
        saving={saving}
        saveSuccess={saveSuccess}
        saveError={saveError}
        saveConflictState={saveConflict ? (saveConflict.remoteLoaded ? 'remoteLoaded' : 'detected') : 'none'}
        conflictBusy={conflictBusy}
        onLoadLatestAfterConflict={saveConflict ? handleLoadLatestAfterConflict : undefined}
        onRestoreConflictDraft={saveConflict?.remoteLoaded ? handleRestoreConflictDraft : undefined}
        onCopyConflictDraft={saveConflict ? handleCopyConflictDraft : undefined}
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
        autoSaveBeforeAgentSend={autoSaveBeforeAgentSend}
        onToggleAutoSaveBeforeAgentSend={setAutoSaveBeforeAgentSend}
        cursorPosition={cursorPosition}
        fileInfo={{
          encoding: content.encoding,
          mimeType: content.mime_type,
          size: formatFileSize(content.size)
        }}
        chatSidebarOpen={chatSidebarOpen}
        onToggleChatSidebar={onToggleChatSidebar}
        onInsertToChat={handleInsertToChat}
        insertToChatDisabled={!content || isInsertingToChat}
        insertToChatTitle={insertToChatTitle}
        onInlineRewrite={handleToggleInlineRewrite}
        inlineRewriteDisabled={!content || inlineRewriteStreaming || projectWorkflowRunning}
        inlineRewriteTitle={inlineRewriteTitle}
        onProjectWorkflow={handleToggleProjectWorkflow}
        projectWorkflowDisabled={!content || projectWorkflowRunning || inlineRewriteStreaming}
        projectWorkflowTitle={t('projectWorkflow.button')}
      />

      <InlineRewritePanel
        isOpen={inlineRewriteOpen}
        isStreaming={inlineRewriteStreaming}
        sourceText={inlineRewriteSourceText}
        rewrittenText={inlineRewritePreview}
        error={inlineRewriteError}
        workflows={rewriteWorkflowOptions}
        selectedWorkflowId={inlineRewriteWorkflowId}
        workflowLoading={inlineRewriteWorkflowsLoading}
        workflowInputs={inlineRewriteWorkflowInputs}
        inputValues={inlineRewriteInputs}
        favorites={launcherFavorites}
        recents={launcherRecents}
        recommendationContext={inlineRewriteRecommendationContext}
        onWorkflowChange={handleInlineRewriteWorkflowChange}
        onToggleFavorite={toggleLauncherFavorite}
        onInputChange={handleInlineRewriteInputChange}
        onGenerate={handleStartInlineRewrite}
        onStop={handleStopInlineRewrite}
        showNoSelectionPrompt={inlineRewriteNoSelectionPromptOpen}
        onNoSelectionRunEmpty={handleNoSelectionRunEmpty}
        onNoSelectionRunFullFile={handleNoSelectionRunFullFile}
        onNoSelectionRunCancel={handleNoSelectionRunCancel}
        onAccept={handleAcceptInlineRewrite}
        onReject={handleCloseInlineRewrite}
        onClose={handleCloseInlineRewrite}
        onOpenWorkflows={handleOpenWorkflowsPage}
      />
      <ProjectWorkflowPanel
        projectId={projectId}
        currentFilePath={content?.path || null}
        isOpen={projectWorkflowOpen}
        isRunning={projectWorkflowRunning}
        workflows={projectPipelineWorkflowOptions}
        selectedWorkflowId={projectWorkflowId}
        workflowLoading={inlineRewriteWorkflowsLoading}
        workflowInputs={projectWorkflowInputDefs}
        inputValues={projectWorkflowInputs}
        artifactPath={projectWorkflowArtifactPath}
        writeMode={projectWorkflowWriteMode}
        output={projectWorkflowOutput}
        error={projectWorkflowError}
        favorites={launcherFavorites}
        recents={launcherRecents}
        recommendationContext={projectWorkflowRecommendationContext}
        onWorkflowChange={handleProjectWorkflowChange}
        onToggleFavorite={toggleLauncherFavorite}
        onInputChange={handleProjectWorkflowInputChange}
        onArtifactPathChange={setProjectWorkflowArtifactPath}
        onWriteModeChange={setProjectWorkflowWriteMode}
        onRun={handleRunProjectWorkflow}
        onStop={handleStopProjectWorkflow}
        onClose={handleCloseProjectWorkflow}
        onOpenWorkflows={handleOpenWorkflowsPage}
      />

      {/* Editor */}
      <div className="flex-1 min-h-0 w-full min-w-0 overflow-hidden">
        <CodeMirror
          className="h-full"
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
