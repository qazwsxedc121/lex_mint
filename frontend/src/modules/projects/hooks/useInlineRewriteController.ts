import { useCallback, useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import type { EditorView } from '@codemirror/view';
import type { FileContent } from '../../../types/project';
import type { Workflow, WorkflowInputDef } from '../../../types/workflow';
import { cancelAsyncRun, listWorkflows, runWorkflowStream } from '../../../services/api';
import { useWorkflowLauncherStorage } from '../../../shared/workflow-launcher/storage';
import type { LauncherRecommendationContext } from '../../../shared/workflow-launcher/types';
import { getProjectWorkspacePath } from '../workspace';

const INLINE_REWRITE_CONTEXT_CHARS = 1200;
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

type RewriteSourceMode = 'selection' | 'empty' | 'full_file';

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

interface WorkflowLaunchPayload {
  source: 'file-viewer';
  filePath: string;
  selectedText?: string;
  selectionStart?: number;
  selectionEnd?: number;
}

interface ChatNavigation {
  navigateToSession?: (sessionId: string) => void;
}

interface UseInlineRewriteControllerParams {
  projectId: string;
  content: FileContent | null;
  value: string;
  editorViewRef: MutableRefObject<EditorView | null>;
  currentSessionId: string | null | undefined;
  createTemporarySession: () => Promise<string>;
  navigation?: ChatNavigation | null;
  queueWorkflowLaunch: (projectId: string, payload: WorkflowLaunchPayload) => void;
}

const normalizeAutoKey = (key: string): string => key.replace(/^_+/, '').toLowerCase();
const isSelectionInputKey = (key: string): boolean => PRIMARY_REWRITE_INPUT_KEYS.has(normalizeAutoKey(key));
const isSliceAutoKey = (key: string): boolean => {
  const normalizedKey = normalizeAutoKey(key);
  return normalizedKey === 'full_text' || AUTO_SLICE_KEY_PATTERN.test(normalizedKey);
};
const isAutoRewriteInputKey = (key: string): boolean =>
  key.startsWith('_') || LEGACY_AUTO_REWRITE_INPUT_KEYS.has(key.toLowerCase()) || isSliceAutoKey(key);

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
    return direction === 'head'
      ? fullText.slice(0, take)
      : fullText.slice(Math.max(fullText.length - take, 0));
  }

  const boundedPercent = Math.min(100, Math.max(0, Math.floor(parsedAmount)));
  const take = Math.ceil(fullText.length * (boundedPercent / 100));
  return direction === 'head'
    ? fullText.slice(0, take)
    : fullText.slice(Math.max(fullText.length - take, 0));
};

const getLanguageTag = (path: string): string => {
  const ext = path.split('.').pop()?.toLowerCase() || '';
  const languageMap: Record<string, string> = {
    py: 'python',
    ts: 'ts',
    tsx: 'tsx',
    js: 'js',
    jsx: 'jsx',
    json: 'json',
    html: 'html',
    css: 'css',
    md: 'markdown',
    yml: 'yaml',
    yaml: 'yaml',
    txt: 'text',
  };

  return languageMap[ext] || ext;
};

export const useInlineRewriteController = ({
  projectId,
  content,
  value,
  editorViewRef,
  currentSessionId,
  createTemporarySession,
  navigation,
  queueWorkflowLaunch,
}: UseInlineRewriteControllerParams) => {
  const { t } = useTranslation('projects');
  const navigate = useNavigate();
  const { favoritesSet, recents, toggleFavorite, addRecent } = useWorkflowLauncherStorage();

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
  const [inlineRewriteRunId, setInlineRewriteRunId] = useState<string | null>(null);

  const inlineRewriteAbortRef = useRef<AbortController | null>(null);
  const rewriteSelectionRef = useRef<RewriteSelectionSnapshot | null>(null);

  useEffect(() => {
    setInlineRewriteOpen(false);
    setInlineRewriteStreaming(false);
    setInlineRewriteError(null);
    setInlineRewriteNoSelectionPromptOpen(false);
    setInlineRewriteInputs({});
    setInlineRewriteSourceText('');
    setInlineRewritePreview('');
    rewriteSelectionRef.current = null;
  }, [content]);

  useEffect(() => {
    setInlineRewriteRunId(null);
  }, [projectId]);

  useEffect(() => {
    return () => {
      inlineRewriteAbortRef.current?.abort();
      inlineRewriteAbortRef.current = null;
    };
  }, []);

  const ensureInlineRewriteSession = useCallback(async () => {
    if (currentSessionId) {
      return currentSessionId;
    }

    try {
      const newSessionId = await createTemporarySession();
      navigation?.navigateToSession?.(newSessionId);
      return newSessionId;
    } catch (err) {
      console.error('Failed to create temporary project session for inline rewrite:', err);
      setInlineRewriteError(t('inlineRewrite.createSessionFailed'));
      return null;
    }
  }, [createTemporarySession, currentSessionId, navigation, t]);

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
  }, [content, editorViewRef]);

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

      const contextBefore = view.state.doc.sliceString(Math.max(0, cursor - INLINE_REWRITE_CONTEXT_CHARS), cursor);
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
    [content, editorViewRef]
  );

  const rewriteWorkflowOptions = useMemo(
    () => inlineRewriteWorkflows.filter((workflow) => workflow.enabled && workflow.scenario === 'editor_rewrite'),
    [inlineRewriteWorkflows]
  );

  const activeRewriteWorkflow = useMemo(() => {
    if (rewriteWorkflowOptions.length === 0) {
      return null;
    }
    return rewriteWorkflowOptions.find((workflow) => workflow.id === inlineRewriteWorkflowId) || rewriteWorkflowOptions[0];
  }, [inlineRewriteWorkflowId, rewriteWorkflowOptions]);

  const inlineRewriteWorkflowInputs = useMemo(() => {
    if (!activeRewriteWorkflow) {
      return [] as WorkflowInputDef[];
    }
    return activeRewriteWorkflow.input_schema.filter((inputDef) => !isAutoRewriteInputKey(inputDef.key));
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

  const inlineRewriteWorkflowNodeIds = useMemo(() => {
    if (!activeRewriteWorkflow) {
      return [] as string[];
    }
    const seen = new Set<string>();
    const ids: string[] = [];
    activeRewriteWorkflow.nodes.forEach((node) => {
      const nodeId = node.id.trim();
      if (!nodeId || seen.has(nodeId)) {
        return;
      }
      seen.add(nodeId);
      ids.push(nodeId);
    });
    return ids;
  }, [activeRewriteWorkflow]);

  const buildInlineRewriteDefaultInputs = useCallback((workflow: Workflow): Record<string, unknown> => {
    const defaults: Record<string, unknown> = {};
    for (const inputDef of workflow.input_schema) {
      if (!isAutoRewriteInputKey(inputDef.key) && inputDef.default !== undefined) {
        defaults[inputDef.key] = inputDef.default;
      }
    }
    return defaults;
  }, []);

  const buildInlineRewriteAutoInputs = useCallback(
    (workflow: Workflow, snapshot: RewriteSelectionSnapshot, fullText: string, sessionId?: string | null) => {
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
        if (slicedValue !== null) {
          assignAutoValueWithAliases(autoValues, inputDef.key, slicedValue);
        }
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
      const rewriteWorkflows = workflows.filter((workflow) => workflow.enabled && workflow.scenario === 'editor_rewrite');
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
        const defaultWorkflow = rewriteWorkflows.find((workflow) => workflow.id === DEFAULT_INLINE_REWRITE_WORKFLOW_ID);
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

  useEffect(() => {
    if (!activeRewriteWorkflow) {
      setInlineRewriteInputs({});
      return;
    }
    setInlineRewriteInputs(buildInlineRewriteDefaultInputs(activeRewriteWorkflow));
  }, [activeRewriteWorkflow, buildInlineRewriteDefaultInputs]);

  const handleInlineRewriteWorkflowChange = useCallback((workflowId: string) => {
    if (!inlineRewriteStreaming) {
      setInlineRewriteWorkflowId(workflowId);
      setInlineRewriteError(null);
      setInlineRewritePreview('');
    }
  }, [inlineRewriteStreaming]);

  const handleInlineRewriteInputChange = useCallback((key: string, nextValue: unknown) => {
    setInlineRewriteInputs((previous) => {
      const next = { ...previous };
      if (nextValue === undefined) {
        delete next[key];
      } else {
        next[key] = nextValue;
      }
      return next;
    });
  }, []);

  const workflowRequiresSelection = useCallback((workflow: Workflow): boolean => {
    return workflow.input_schema.some((inputDef) => inputDef.required && isSelectionInputKey(inputDef.key));
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
        let inputValue = runInputs[inputDef.key];
        if (inputValue === undefined && inputDef.default !== undefined) {
          inputValue = inputDef.default;
        }

        if (inputValue === undefined || inputValue === null || (inputDef.type !== 'string' && inputValue === '')) {
          if (inputDef.required) {
            return { inputs: runInputs, error: t('inlineRewrite.missingRequiredInput', { key: inputDef.key }) };
          }
          continue;
        }

        if (inputDef.type === 'string') {
          const stringValue = typeof inputValue === 'string' ? inputValue : String(inputValue);
          if (typeof inputDef.max_length === 'number' && stringValue.length > inputDef.max_length) {
            return { inputs: runInputs, error: `${inputDef.key} exceeds max length (${inputDef.max_length})` };
          }
          if (typeof inputDef.pattern === 'string' && inputDef.pattern.trim()) {
            try {
              if (!new RegExp(inputDef.pattern).test(stringValue)) {
                return { inputs: runInputs, error: `${inputDef.key} format is invalid` };
              }
            } catch {
              return { inputs: runInputs, error: `${inputDef.key} has invalid pattern config` };
            }
          }
          runInputs[inputDef.key] = stringValue;
          continue;
        }

        if (inputDef.type === 'number') {
          if (typeof inputValue !== 'number' || Number.isNaN(inputValue)) {
            return { inputs: runInputs, error: t('inlineRewrite.invalidNumberInput', { key: inputDef.key }) };
          }
          runInputs[inputDef.key] = inputValue;
          continue;
        }

        if (inputDef.type === 'boolean') {
          if (typeof inputValue !== 'boolean') {
            return { inputs: runInputs, error: t('inlineRewrite.invalidBooleanInput', { key: inputDef.key }) };
          }
          runInputs[inputDef.key] = inputValue;
          continue;
        }

        if (typeof inputValue !== 'string' || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(inputValue)) {
          return { inputs: runInputs, error: t('inlineRewrite.invalidNodeInput', { key: inputDef.key }) };
        }
        const hasTargetNode = workflow.nodes.some((node) => node.id === inputValue);
        if (!hasTargetNode) {
          return { inputs: runInputs, error: t('inlineRewrite.invalidNodeInput', { key: inputDef.key }) };
        }
        runInputs[inputDef.key] = inputValue;
      }

      return { inputs: runInputs };
    },
    [buildInlineRewriteAutoInputs, inlineRewriteInputs, t]
  );

  const handleOpenInlineRewrite = useCallback(() => {
    void ensureInlineRewriteWorkflowsLoaded();
    const snapshot = getInlineRewriteSelectionSnapshot();
    setInlineRewriteOpen(true);
    setInlineRewriteError(null);
    setInlineRewriteNoSelectionPromptOpen(false);

    if (activeRewriteWorkflow) {
      setInlineRewriteInputs(buildInlineRewriteDefaultInputs(activeRewriteWorkflow));
    }

    setInlineRewriteSourceText(snapshot?.selectedText || '');
    setInlineRewritePreview('');
  }, [activeRewriteWorkflow, buildInlineRewriteDefaultInputs, ensureInlineRewriteWorkflowsLoaded, getInlineRewriteSelectionSnapshot]);

  const handleStopInlineRewrite = useCallback(() => {
    inlineRewriteAbortRef.current?.abort();
    inlineRewriteAbortRef.current = null;
    setInlineRewriteStreaming(false);
    const runId = inlineRewriteRunId;
    setInlineRewriteRunId(null);
    if (runId) {
      void cancelAsyncRun(runId).catch(() => {
        // Ignore cancel errors when run already finished.
      });
    }
  }, [inlineRewriteRunId]);

  const handleCloseInlineRewrite = useCallback(() => {
    handleStopInlineRewrite();
    setInlineRewriteOpen(false);
    setInlineRewriteError(null);
    setInlineRewriteNoSelectionPromptOpen(false);
    setInlineRewritePreview('');
    rewriteSelectionRef.current = null;
  }, [handleStopInlineRewrite]);

  const handleToggleInlineRewrite = useCallback(() => {
    if (inlineRewriteOpen) {
      handleCloseInlineRewrite();
    } else {
      handleOpenInlineRewrite();
    }
  }, [handleCloseInlineRewrite, handleOpenInlineRewrite, inlineRewriteOpen]);

  const handleOpenProjectWorkflowWorkspace = useCallback(() => {
    if (!content) {
      return;
    }
    const selectionSnapshot = getInlineRewriteSelectionSnapshot();
    queueWorkflowLaunch(projectId, {
      source: 'file-viewer',
      filePath: content.path,
      selectedText: selectionSnapshot?.selectedText,
      selectionStart: selectionSnapshot?.from,
      selectionEnd: selectionSnapshot?.to,
    });
    navigate(getProjectWorkspacePath(projectId, 'workflows'));
  }, [content, getInlineRewriteSelectionSnapshot, navigate, projectId, queueWorkflowLaunch]);

  const handleOpenWorkflowsPage = useCallback(() => {
    navigate('/workflows');
  }, [navigate]);

  const handleStartInlineRewrite = useCallback(async (noSelectionMode: 'ask' | 'empty' | 'full_file' = 'ask') => {
    if (inlineRewriteStreaming || !content) {
      return;
    }

    const availableWorkflows = rewriteWorkflowOptions.length > 0
      ? rewriteWorkflowOptions
      : await ensureInlineRewriteWorkflowsLoaded();
    if (availableWorkflows.length === 0) {
      setInlineRewriteOpen(true);
      setInlineRewriteError(t('inlineRewrite.noWorkflows'));
      return;
    }

    const workflowToRun = availableWorkflows.find((workflow) => workflow.id === inlineRewriteWorkflowId) || availableWorkflows[0];
    let snapshot = getInlineRewriteSelectionSnapshot();
    if (!snapshot) {
      const requiresSelection = workflowRequiresSelection(workflowToRun);
      if (requiresSelection && noSelectionMode === 'ask') {
        setInlineRewriteNoSelectionPromptOpen(true);
        setInlineRewriteError(null);
        return;
      }
      snapshot = getInlineRewriteSnapshotForNoSelection(noSelectionMode === 'full_file' ? 'full_file' : 'empty');
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
    setInlineRewriteRunId(null);

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
          onRunCreated: setInlineRewriteRunId,
          onChunk: (chunk) => setInlineRewritePreview((previous) => previous + chunk),
          onComplete: () => {
            setInlineRewriteStreaming(false);
            setInlineRewriteRunId(null);
            addRecent(workflowToRun.id);
          },
          onError: (errorMessage) => {
            setInlineRewriteStreaming(false);
            setInlineRewriteRunId(null);
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
      setInlineRewriteRunId(null);
      setInlineRewriteError(err instanceof Error ? err.message : t('inlineRewrite.requestFailed'));
    } finally {
      setInlineRewriteStreaming(false);
    }
  }, [
    addRecent,
    buildInlineRewriteRunInputs,
    content,
    editorViewRef,
    ensureInlineRewriteSession,
    ensureInlineRewriteWorkflowsLoaded,
    getInlineRewriteSelectionSnapshot,
    getInlineRewriteSnapshotForNoSelection,
    inlineRewriteStreaming,
    inlineRewriteWorkflowId,
    projectId,
    rewriteWorkflowOptions,
    t,
    value,
    workflowRequiresSelection,
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
    if (view.state.doc.sliceString(selectionSnapshot.from, selectionSnapshot.to) !== selectionSnapshot.selectedText) {
      setInlineRewriteError(t('inlineRewrite.selectionChanged'));
      return;
    }

    view.dispatch({
      changes: { from: selectionSnapshot.from, to: selectionSnapshot.to, insert: rewrittenText },
      selection: { anchor: selectionSnapshot.from, head: selectionSnapshot.from + rewrittenText.length },
    });
    view.focus();

    setInlineRewriteOpen(false);
    setInlineRewriteError(null);
    setInlineRewritePreview('');
    rewriteSelectionRef.current = null;
  }, [editorViewRef, inlineRewritePreview, t]);

  return {
    favorites: favoritesSet,
    recents,
    toggleFavorite,
    inlineRewriteOpen,
    inlineRewriteStreaming,
    inlineRewriteError,
    inlineRewriteNoSelectionPromptOpen,
    inlineRewriteInputs,
    inlineRewriteSourceText,
    inlineRewritePreview,
    rewriteWorkflowOptions,
    inlineRewriteWorkflowsLoading,
    inlineRewriteWorkflowInputs,
    inlineRewriteWorkflowNodeIds,
    inlineRewriteRecommendationContext,
    selectedWorkflowId: inlineRewriteWorkflowId,
    handleInlineRewriteWorkflowChange,
    handleInlineRewriteInputChange,
    handleToggleInlineRewrite,
    handleOpenProjectWorkflowWorkspace,
    handleOpenWorkflowsPage,
    handleStartInlineRewrite,
    handleStopInlineRewrite,
    handleNoSelectionRunEmpty,
    handleNoSelectionRunFullFile,
    handleNoSelectionRunCancel,
    handleAcceptInlineRewrite,
    handleCloseInlineRewrite,
  };
};
