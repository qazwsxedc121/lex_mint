/**
 * InlineRewritePanel - Rewrite selected editor content with streaming preview and diff.
 */

import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { WorkflowInputDef } from '../../../types/workflow';

type DiffType = 'same' | 'add' | 'remove';

interface DiffLine {
  type: DiffType;
  text: string;
}

interface InlineRewritePanelProps {
  isOpen: boolean;
  isStreaming: boolean;
  sourceText: string;
  rewrittenText: string;
  error: string | null;
  workflowOptions: Array<{ id: string; name: string }>;
  selectedWorkflowId: string;
  workflowLoading: boolean;
  workflowInputs: WorkflowInputDef[];
  inputValues: Record<string, unknown>;
  onWorkflowChange: (workflowId: string) => void;
  onInputChange: (key: string, value: unknown) => void;
  onGenerate: () => void;
  onStop: () => void;
  onAccept: () => void;
  onReject: () => void;
  onClose: () => void;
}

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
  isOpen,
  isStreaming,
  sourceText,
  rewrittenText,
  error,
  workflowOptions,
  selectedWorkflowId,
  workflowLoading,
  workflowInputs,
  inputValues,
  onWorkflowChange,
  onInputChange,
  onGenerate,
  onStop,
  onAccept,
  onReject,
  onClose,
}) => {
  const { t } = useTranslation('projects');

  const diffLines = useMemo(
    () => buildLineDiff(sourceText, rewrittenText),
    [sourceText, rewrittenText]
  );
  const hasRewriteResult = rewrittenText.length > 0;
  const canGenerate = workflowOptions.length > 0 && !workflowLoading;

  if (!isOpen) {
    return null;
  }

  return (
    <div
      data-name="inline-rewrite-panel"
      className="border-b border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-3 space-y-3"
    >
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
          {t('inlineRewrite.title')}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          {t('common:close')}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-2">
        <label className="text-xs text-gray-600 dark:text-gray-400 self-center" htmlFor="inline-rewrite-workflow">
          {t('inlineRewrite.workflowLabel')}
        </label>
        <select
          id="inline-rewrite-workflow"
          data-name="inline-rewrite-workflow"
          value={selectedWorkflowId}
          onChange={(event) => onWorkflowChange(event.target.value)}
          disabled={workflowLoading || workflowOptions.length === 0}
          className="text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 disabled:bg-gray-100 dark:disabled:bg-gray-800/50 disabled:text-gray-500"
        >
          {workflowOptions.length === 0 ? (
            <option value="">{workflowLoading ? t('inlineRewrite.loadingWorkflows') : t('inlineRewrite.noWorkflows')}</option>
          ) : (
            workflowOptions.map((workflow) => (
              <option key={workflow.id} value={workflow.id}>
                {workflow.name}
              </option>
            ))
          )}
        </select>
      </div>

      {workflowInputs.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-2" data-name="inline-rewrite-workflow-inputs">
          <div className="text-xs text-gray-600 dark:text-gray-400 self-start pt-2">
            {t('inlineRewrite.workflowInputsLabel')}
          </div>
          <div className="space-y-2">
            {workflowInputs.map((field) => {
              const rawValue = inputValues[field.key];
              const keyLabel = field.required
                ? `${field.key} (${t('inlineRewrite.required')})`
                : field.key;
              const inputName = `inline-rewrite-input-${field.key}`;

              if (field.type === 'boolean') {
                const selectValue = rawValue === true ? 'true' : rawValue === false ? 'false' : '';
                return (
                  <label key={field.key} className="block space-y-1" htmlFor={inputName}>
                    <div className="text-xs text-gray-700 dark:text-gray-300">{keyLabel}</div>
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
                  </label>
                );
              }

              if (field.type === 'number') {
                const inputValue = typeof rawValue === 'number' ? String(rawValue) : '';
                return (
                  <label key={field.key} className="block space-y-1" htmlFor={inputName}>
                    <div className="text-xs text-gray-700 dark:text-gray-300">{keyLabel}</div>
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
                  </label>
                );
              }

              const stringValue = typeof rawValue === 'string' ? rawValue : '';
              return (
                <label key={field.key} className="block space-y-1" htmlFor={inputName}>
                  <div className="text-xs text-gray-700 dark:text-gray-300">{keyLabel}</div>
                  <textarea
                    id={inputName}
                    data-name={inputName}
                    rows={2}
                    value={stringValue}
                    onChange={(event) => onInputChange(field.key, event.target.value)}
                    className="w-full text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  />
                </label>
              );
            })}
          </div>
        </div>
      )}

      {error && (
        <div className="text-xs text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded px-2 py-1.5">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {!isStreaming ? (
          <button
            type="button"
            data-name="inline-rewrite-generate"
            onClick={onGenerate}
            disabled={!canGenerate}
            className="px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed"
          >
            {t('inlineRewrite.generate')}
          </button>
        ) : (
          <button
            type="button"
            data-name="inline-rewrite-stop"
            onClick={onStop}
            className="px-3 py-1.5 rounded text-xs font-medium border border-amber-500 text-amber-700 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/20"
          >
            {t('inlineRewrite.stop')}
          </button>
        )}
        <button
          type="button"
          data-name="inline-rewrite-accept"
          onClick={onAccept}
          disabled={isStreaming || !hasRewriteResult}
          className="px-3 py-1.5 rounded text-xs font-medium bg-green-600 hover:bg-green-700 text-white disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed"
        >
          {t('inlineRewrite.accept')}
        </button>
        <button
          type="button"
          data-name="inline-rewrite-reject"
          onClick={onReject}
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
  );
};
