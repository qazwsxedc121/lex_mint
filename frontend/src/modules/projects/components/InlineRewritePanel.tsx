/**
 * InlineRewritePanel - Rewrite selected editor content with streaming preview and diff.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { DocumentIcon, FolderOpenIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { readFile } from '../../../services/api';
import type { Workflow, WorkflowInputDef } from '../../../types/workflow';
import { WorkflowLauncherList } from '../../../shared/workflow-launcher/WorkflowLauncherList';
import type { LauncherRecentItem, LauncherRecommendationContext } from '../../../shared/workflow-launcher/types';
import { FilePickerDialog } from './FilePickerDialog';

type DiffType = 'same' | 'add' | 'remove';

interface DiffLine {
  type: DiffType;
  text: string;
}

interface InlineRewritePanelProps {
  projectId: string;
  currentFilePath?: string | null;
  isOpen: boolean;
  isStreaming: boolean;
  sourceText: string;
  rewrittenText: string;
  error: string | null;
  workflows: Workflow[];
  selectedWorkflowId: string;
  workflowLoading: boolean;
  workflowInputs: WorkflowInputDef[];
  inputValues: Record<string, unknown>;
  favorites: Set<string>;
  recents: LauncherRecentItem[];
  recommendationContext: LauncherRecommendationContext;
  onWorkflowChange: (workflowId: string) => void;
  onToggleFavorite: (workflowId: string) => void;
  onInputChange: (key: string, value: unknown) => void;
  onGenerate: () => void;
  onStop: () => void;
  showNoSelectionPrompt: boolean;
  onNoSelectionRunEmpty: () => void;
  onNoSelectionRunFullFile: () => void;
  onNoSelectionRunCancel: () => void;
  onAccept: () => void;
  onReject: () => void;
  onClose: () => void;
  onOpenWorkflows: () => void;
}

interface FileBackedInputMeta {
  path: string;
}

const isIdentifierLikeField = (fieldKey: string): boolean => {
  const normalized = fieldKey.trim().toLowerCase();
  return normalized === 'id' || normalized.endsWith('_id');
};

const canInsertFileForInput = (field: WorkflowInputDef): boolean => {
  if (field.type !== 'string') {
    return false;
  }
  if (typeof field.allow_file_insert === 'boolean') {
    return field.allow_file_insert;
  }
  // Backward-compatible safety for old schemas without explicit allow_file_insert.
  return !isIdentifierLikeField(field.key);
};

function splitLines(value: string): string[] {
  return value.split('\n');
}

function buildLineDiff(sourceText: string, rewrittenText: string): DiffLine[] {
  const sourceLines = splitLines(sourceText);
  const rewrittenLines = splitLines(rewrittenText);
  const complexity = sourceLines.length * rewrittenLines.length;

  if (complexity > 160000) {
    return [
      { type: 'remove', text: sourceText },
      { type: 'add', text: rewrittenText },
    ];
  }

  const rows = sourceLines.length + 1;
  const cols = rewrittenLines.length + 1;
  const dp: number[][] = Array.from({ length: rows }, () => Array<number>(cols).fill(0));

  for (let i = sourceLines.length - 1; i >= 0; i -= 1) {
    for (let j = rewrittenLines.length - 1; j >= 0; j -= 1) {
      if (sourceLines[i] === rewrittenLines[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  const diff: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < sourceLines.length && j < rewrittenLines.length) {
    if (sourceLines[i] === rewrittenLines[j]) {
      diff.push({ type: 'same', text: sourceLines[i] });
      i += 1;
      j += 1;
      continue;
    }

    if (dp[i + 1][j] >= dp[i][j + 1]) {
      diff.push({ type: 'remove', text: sourceLines[i] });
      i += 1;
      continue;
    }

    diff.push({ type: 'add', text: rewrittenLines[j] });
    j += 1;
  }

  while (i < sourceLines.length) {
    diff.push({ type: 'remove', text: sourceLines[i] });
    i += 1;
  }
  while (j < rewrittenLines.length) {
    diff.push({ type: 'add', text: rewrittenLines[j] });
    j += 1;
  }

  return diff;
}

function diffLineClass(type: DiffType): string {
  if (type === 'add') {
    return 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200';
  }
  if (type === 'remove') {
    return 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200';
  }
  return 'text-gray-700 dark:text-gray-300';
}

function diffLinePrefix(type: DiffType): string {
  if (type === 'add') return '+';
  if (type === 'remove') return '-';
  return ' ';
}

export const InlineRewritePanel: React.FC<InlineRewritePanelProps> = ({
  projectId,
  currentFilePath = null,
  isOpen,
  isStreaming,
  sourceText,
  rewrittenText,
  error,
  workflows,
  selectedWorkflowId,
  workflowLoading,
  workflowInputs,
  inputValues,
  favorites,
  recents,
  recommendationContext,
  onWorkflowChange,
  onToggleFavorite,
  onInputChange,
  onGenerate,
  onStop,
  showNoSelectionPrompt,
  onNoSelectionRunEmpty,
  onNoSelectionRunFullFile,
  onNoSelectionRunCancel,
  onAccept,
  onReject,
  onClose,
  onOpenWorkflows,
}) => {
  const { t } = useTranslation('projects');
  const [pickerFieldKey, setPickerFieldKey] = useState<string | null>(null);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const [loadingFieldKey, setLoadingFieldKey] = useState<string | null>(null);
  const [fileBackedInputs, setFileBackedInputs] = useState<Record<string, FileBackedInputMeta>>({});
  const diffLines = useMemo(
    () => buildLineDiff(sourceText, rewrittenText),
    [sourceText, rewrittenText]
  );
  const hasRewriteResult = rewrittenText.length > 0;
  const canGenerate = workflows.length > 0 && !workflowLoading;
  const activeFieldLoading = useMemo(
    () => Boolean(loadingFieldKey && pickerFieldKey === loadingFieldKey),
    [loadingFieldKey, pickerFieldKey]
  );

  useEffect(() => {
    if (!isOpen) {
      setPickerFieldKey(null);
      setPickerError(null);
      setLoadingFieldKey(null);
      setFileBackedInputs({});
    }
  }, [isOpen]);

  useEffect(() => {
    if (!pickerFieldKey) {
      return;
    }
    if (!workflowInputs.some((field) => field.key === pickerFieldKey)) {
      setPickerFieldKey(null);
      setPickerError(null);
      setLoadingFieldKey(null);
    }
  }, [pickerFieldKey, workflowInputs]);

  useEffect(() => {
    const validKeys = new Set(workflowInputs.map((field) => field.key));
    setFileBackedInputs((previous) => {
      let changed = false;
      const next: Record<string, FileBackedInputMeta> = {};
      Object.entries(previous).forEach(([key, metadata]) => {
        if (validKeys.has(key)) {
          next[key] = metadata;
        } else {
          changed = true;
        }
      });
      return changed ? next : previous;
    });
  }, [workflowInputs]);

  const handleToggleFilePicker = (fieldKey: string) => {
    if (pickerFieldKey === fieldKey) {
      setPickerFieldKey(null);
      setPickerError(null);
      return;
    }
    setPickerFieldKey(fieldKey);
    setPickerError(null);
  };

  const handleSelectFileForInput = async (filePath: string) => {
    if (!projectId || !pickerFieldKey) {
      return;
    }
    const targetFieldKey = pickerFieldKey;
    setLoadingFieldKey(targetFieldKey);
    setPickerError(null);
    try {
      const fileData = await readFile(projectId, filePath);
      onInputChange(targetFieldKey, fileData.content);
      setFileBackedInputs((previous) => ({
        ...previous,
        [targetFieldKey]: {
          path: filePath,
        },
      }));
      setPickerFieldKey(null);
    } catch (error) {
      console.error('Failed to load inline rewrite input file:', error);
      setPickerError(t('projectWorkflow.loadFileFailed'));
    } finally {
      setLoadingFieldKey(null);
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div
      data-name="inline-rewrite-panel"
      className="border-b border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-3 space-y-3"
    >
      <div data-name="workflow-launcher-panel" className="space-y-3">
      <div className="space-y-2">
        {/* Keep legacy selector in DOM for backward compatibility. */}
        <div className="sr-only">
          <label className="text-xs text-gray-600 dark:text-gray-400 self-center" htmlFor="inline-rewrite-workflow">
            {t('inlineRewrite.workflowLabel')}
          </label>
          <select
            id="inline-rewrite-workflow"
            data-name="inline-rewrite-workflow"
            value={selectedWorkflowId}
            onChange={(event) => onWorkflowChange(event.target.value)}
            disabled={workflowLoading || workflows.length === 0 || isStreaming}
            className="text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 disabled:bg-gray-100 dark:disabled:bg-gray-800/50 disabled:text-gray-500"
          >
            {workflows.length === 0 ? (
              <option value="">
                {workflowLoading ? t('inlineRewrite.loadingWorkflows') : t('inlineRewrite.noWorkflows')}
              </option>
            ) : (
              workflows.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.name}
                </option>
              ))
            )}
          </select>
        </div>

        <WorkflowLauncherList
          workflows={workflows}
          selectedWorkflowId={selectedWorkflowId || null}
          loading={workflowLoading}
          selectionLocked={isStreaming}
          namespace="projects"
          compact
          showSearch
          maxWidthClassName="max-w-full xl:max-w-[920px]"
          headerActions={(
            <button
              type="button"
              onClick={onClose}
              className="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              {t('common:close')}
            </button>
          )}
          favorites={favorites}
          recents={recents}
          recommendationContext={recommendationContext}
          onSelect={onWorkflowChange}
          onToggleFavorite={onToggleFavorite}
          emptyMessage={t('inlineRewrite.noWorkflows')}
        />

        {!workflowLoading && workflows.length === 0 && (
          <div className="rounded-md border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/60 p-3">
            <div className="text-xs text-gray-600 dark:text-gray-300">{t('workflowLauncher.emptyHint')}</div>
            <button
              type="button"
              onClick={onOpenWorkflows}
              className="mt-2 px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white"
            >
              {t('workflowLauncher.openWorkflows')}
            </button>
          </div>
        )}
      </div>

      {workflowInputs.length > 0 && (
        <div
          data-name="inline-rewrite-workflow-inputs"
          className="relative rounded border border-gray-300 dark:border-gray-700 bg-gray-50/70 dark:bg-gray-800/30 px-3 pb-3 pt-4"
        >
          <div className="absolute -top-2 left-3 px-1 text-xs text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-900">
            {t('inlineRewrite.workflowInputsLabel')}
          </div>
          <div className="space-y-2">
            {workflowInputs.map((field) => {
              const rawValue = inputValues[field.key];
              const keyLabel = field.required
                ? `${field.key} (${t('inlineRewrite.required')})`
                : field.key;
              const inputName = `inline-rewrite-input-${field.key}`;
              const fileBackedMeta = fileBackedInputs[field.key];

              if (field.type === 'boolean') {
                const selectValue = rawValue === true ? 'true' : rawValue === false ? 'false' : '';
                return (
                  <div key={field.key} className="grid grid-cols-1 lg:grid-cols-[180px_minmax(0,1fr)] items-center gap-2">
                    <label htmlFor={inputName} className="text-xs text-gray-700 dark:text-gray-300">
                      {keyLabel}
                    </label>
                    <select
                      id={inputName}
                      data-name={inputName}
                      value={selectValue}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (!value) {
                          onInputChange(field.key, undefined);
                          return;
                        }
                        onInputChange(field.key, value === 'true');
                      }}
                      className="w-full text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    >
                      <option value="">{t('inlineRewrite.booleanUnset')}</option>
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  </div>
                );
              }

              if (field.type === 'number') {
                const inputValue = typeof rawValue === 'number' ? String(rawValue) : '';
                return (
                  <div key={field.key} className="grid grid-cols-1 lg:grid-cols-[180px_minmax(0,1fr)] items-center gap-2">
                    <label htmlFor={inputName} className="text-xs text-gray-700 dark:text-gray-300">
                      {keyLabel}
                    </label>
                    <input
                      id={inputName}
                      data-name={inputName}
                      type="number"
                      value={inputValue}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (!value.trim()) {
                          onInputChange(field.key, undefined);
                          return;
                        }
                        onInputChange(field.key, Number(value));
                      }}
                      className="w-full text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                );
              }

              const stringValue = typeof rawValue === 'string' ? rawValue : '';
              const canInsertFromFile = canInsertFileForInput(field);
              return (
                <div key={field.key} className="grid grid-cols-1 lg:grid-cols-[180px_minmax(0,1fr)_auto] items-start gap-2">
                  <label htmlFor={inputName} className="text-xs text-gray-700 dark:text-gray-300 lg:pt-1.5">
                    {keyLabel}
                  </label>
                  {fileBackedMeta ? (
                    <div className="w-full min-w-0 rounded border border-blue-200 dark:border-blue-800 bg-blue-50/80 dark:bg-blue-900/20 px-2 py-1.5">
                      <div className="flex items-start gap-2 min-w-0">
                        <DocumentIcon className="h-4 w-4 mt-0.5 text-blue-600 dark:text-blue-300 flex-shrink-0" />
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-medium text-blue-800 dark:text-blue-200">
                            {t('projectWorkflow.insertFromFile')}
                          </div>
                          <div className="text-[11px] text-blue-700/90 dark:text-blue-300 truncate">
                            {fileBackedMeta.path}
                          </div>
                        </div>
                        <button
                          type="button"
                          data-name={`inline-rewrite-file-widget-clear-${field.key}`}
                          onClick={() => {
                            setFileBackedInputs((previous) => {
                              if (!previous[field.key]) {
                                return previous;
                              }
                              const next = { ...previous };
                              delete next[field.key];
                              return next;
                            });
                          }}
                          className="inline-flex h-6 w-6 items-center justify-center rounded border border-blue-200 dark:border-blue-700 bg-white/80 dark:bg-gray-800 text-blue-700 dark:text-blue-300 hover:bg-white dark:hover:bg-gray-700"
                          title={t('common:close')}
                        >
                          <XMarkIcon className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <textarea
                      id={inputName}
                      data-name={inputName}
                      rows={2}
                      value={stringValue}
                      onChange={(event) => {
                        onInputChange(field.key, event.target.value);
                        if (fileBackedInputs[field.key]) {
                          setFileBackedInputs((previous) => {
                            const next = { ...previous };
                            delete next[field.key];
                            return next;
                          });
                        }
                      }}
                      className="w-full min-w-0 text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    />
                  )}
                  {canInsertFromFile ? (
                    <div className="flex shrink-0 items-start gap-1 lg:pt-0.5">
                      <button
                        type="button"
                        data-name={`inline-rewrite-insert-file-${field.key}`}
                        disabled={isStreaming || activeFieldLoading}
                        onClick={() => handleToggleFilePicker(field.key)}
                        title={loadingFieldKey === field.key ? t('projectWorkflow.loadingFile') : t('projectWorkflow.insertFromFile')}
                        className="inline-flex h-7 w-7 items-center justify-center rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:bg-gray-100 dark:disabled:bg-gray-800/60 disabled:text-gray-400 disabled:cursor-not-allowed"
                      >
                        <FolderOpenIcon className="h-4 w-4" />
                      </button>
                    </div>
                  ) : (
                    <div className="hidden lg:block" />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {pickerError && (
        <div className="text-xs text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded px-2 py-1.5">
          {pickerError}
        </div>
      )}

      {error && (
        <div className="text-xs text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded px-2 py-1.5">
          {error}
        </div>
      )}

      {showNoSelectionPrompt && (
        <div
          data-name="inline-rewrite-no-selection-dialog"
          className="rounded border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 px-3 py-2 space-y-2"
        >
          <div className="text-xs font-medium text-amber-900 dark:text-amber-200">
            {t('inlineRewrite.noSelectionPromptTitle')}
          </div>
          <div className="text-xs text-amber-800 dark:text-amber-300">
            {t('inlineRewrite.noSelectionPromptDescription')}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              data-name="inline-rewrite-no-selection-empty"
              onClick={onNoSelectionRunEmpty}
              className="px-3 py-1.5 rounded text-xs font-medium border border-gray-300 dark:border-gray-600 hover:bg-white/80 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200"
            >
              {t('inlineRewrite.noSelectionRunEmpty')}
            </button>
            <button
              type="button"
              data-name="inline-rewrite-no-selection-full"
              onClick={onNoSelectionRunFullFile}
              className="px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white"
            >
              {t('inlineRewrite.noSelectionRunFullFile')}
            </button>
            <button
              type="button"
              data-name="inline-rewrite-no-selection-cancel"
              onClick={onNoSelectionRunCancel}
              className="px-3 py-1.5 rounded text-xs font-medium border border-red-300 dark:border-red-700 text-red-700 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20"
            >
              {t('inlineRewrite.noSelectionRunCancel')}
            </button>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {!isStreaming ? (
          <button
            type="button"
            data-name="inline-rewrite-generate"
            onClick={() => onGenerate()}
            disabled={!canGenerate}
            className="px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed"
          >
            {t('inlineRewrite.generate')}
          </button>
        ) : (
          <button
            type="button"
            data-name="inline-rewrite-stop"
            onClick={() => onStop()}
            className="px-3 py-1.5 rounded text-xs font-medium border border-amber-500 text-amber-700 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/20"
          >
            {t('inlineRewrite.stop')}
          </button>
        )}
        <button
          type="button"
          data-name="inline-rewrite-accept"
          onClick={() => onAccept()}
          disabled={isStreaming || !hasRewriteResult}
          className="px-3 py-1.5 rounded text-xs font-medium bg-green-600 hover:bg-green-700 text-white disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed"
        >
          {t('inlineRewrite.accept')}
        </button>
        <button
          type="button"
          data-name="inline-rewrite-reject"
          onClick={() => onReject()}
          className="px-3 py-1.5 rounded text-xs font-medium border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300"
        >
          {t('inlineRewrite.reject')}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="space-y-1">
          <div className="text-xs font-medium text-gray-700 dark:text-gray-300">
            {t('inlineRewrite.selectionPreview')}
          </div>
          <pre className="text-xs max-h-40 overflow-auto rounded border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-2 whitespace-pre-wrap break-words">
            {sourceText || t('inlineRewrite.emptySelection')}
          </pre>
        </div>

        <div className="space-y-1">
          <div className="text-xs font-medium text-gray-700 dark:text-gray-300">
            {t('inlineRewrite.rewritePreview')}
          </div>
          <pre
            data-name="inline-rewrite-preview"
            className="text-xs max-h-40 overflow-auto rounded border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-2 whitespace-pre-wrap break-words"
          >
            {rewrittenText || t('inlineRewrite.emptyRewrite')}
          </pre>
        </div>
      </div>

      {hasRewriteResult && (
        <div className="space-y-1">
          <div className="text-xs font-medium text-gray-700 dark:text-gray-300">
            {t('inlineRewrite.diffTitle')}
          </div>
          <div
            data-name="inline-rewrite-diff"
            className="max-h-48 overflow-auto rounded border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800"
          >
            {diffLines.map((line, index) => (
              <div
                key={`${line.type}-${index}`}
                className={`px-2 py-0.5 text-xs font-mono whitespace-pre-wrap break-words ${diffLineClass(line.type)}`}
              >
                {diffLinePrefix(line.type)} {line.text}
              </div>
            ))}
          </div>
        </div>
      )}
      </div>

      <FilePickerDialog
        projectId={projectId}
        isOpen={Boolean(pickerFieldKey)}
        title={pickerFieldKey ? `${t('projectWorkflow.insertFromFile')} (${pickerFieldKey})` : t('projectWorkflow.insertFromFile')}
        selectedPath={currentFilePath}
        onClose={() => setPickerFieldKey(null)}
        onSelect={(filePath) => {
          void handleSelectFileForInput(filePath);
        }}
      />
    </div>
  );
};
