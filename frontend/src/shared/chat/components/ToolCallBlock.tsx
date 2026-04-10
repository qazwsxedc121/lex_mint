/**
 * ToolCallBlock component - displays tool/function call info inline.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  ArrowTopRightOnSquareIcon,
  ChevronDownIcon,
  WrenchScrewdriverIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';

import type { ToolCallInfo } from '../../../types/message';
import { useDeveloperMode } from '../../../hooks/useDeveloperMode';
import { applyProjectChatDiff } from '../../../services/api';

interface ToolCallBlockProps {
  toolCalls: ToolCallInfo[];
  sessionId?: string;
}

interface ToolErrorPayload {
  code?: string;
  message?: string;
}

interface ApplyDiffResultPayload {
  ok?: boolean;
  mode?: string;
  file_path?: string;
  base_hash?: string;
  pending_patch_id?: string;
  pending_patch_ttl_seconds?: number;
  pending_patch_expires_at?: number;
  preview?: {
    additions?: number;
    deletions?: number;
    hunks?: number;
  };
  error?: ToolErrorPayload;
}

interface ToolUiField {
  label?: string;
  value?: unknown;
}

interface ToolUiItem {
  title?: string;
  subtitle?: string;
  description?: string;
  url?: string;
}

interface ToolUiSection {
  kind?: 'fields' | 'items' | 'text';
  title?: string;
  fields?: ToolUiField[];
  items?: ToolUiItem[];
  text?: string;
  empty_message?: string;
  truncated?: boolean;
}

interface ToolUiPayload {
  version?: number;
  kind?: string;
  summary?: string;
  status?: 'ok' | 'error';
  error_message?: string;
  sections?: ToolUiSection[];
}

type DiffPreviewLineType = 'meta' | 'hunk' | 'context' | 'add' | 'remove';

interface DiffPreviewLine {
  type: DiffPreviewLineType;
  text: string;
}

interface UnifiedDiffPreview {
  lines: DiffPreviewLine[];
  additions: number;
  deletions: number;
  hunks: number;
  hiddenLineCount: number;
}

const APPLY_DIFF_TOOL_NAMES = new Set([
  'apply_diff_current_document',
  'apply_diff_project_document',
]);
const APPLIED_PATCH_STORAGE_KEY = 'lex-mint.project-chat.applied-patches.v1';
const DISMISSED_PATCH_STORAGE_KEY = 'lex-mint.project-chat.dismissed-patches.v1';
const MAX_DIFF_PREVIEW_LINES = 240;

const readPatchFlags = (storageKey: string): Record<string, boolean> => {
  if (typeof window === 'undefined') {
    return {};
  }
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') {
      return {};
    }
    const flags: Record<string, boolean> = {};
    for (const [patchId, value] of Object.entries(parsed)) {
      if (patchId && value === true) {
        flags[patchId] = true;
      }
    }
    return flags;
  } catch {
    return {};
  }
};

const writePatchFlags = (storageKey: string, flags: Record<string, boolean>) => {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    const patchIds = Object.keys(flags);
    const normalized: Record<string, boolean> = {};
    const start = Math.max(0, patchIds.length - 400);
    for (let i = start; i < patchIds.length; i += 1) {
      normalized[patchIds[i]] = true;
    }
    window.sessionStorage.setItem(storageKey, JSON.stringify(normalized));
  } catch {
    // Ignore storage errors.
  }
};

const parseProjectIdFromPath = (pathname: string): string | null => {
  const match = pathname.match(/^\/projects\/([^/]+)/);
  return match ? match[1] : null;
};

const safeParseJson = <T extends object>(raw?: string): T | null => {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') {
      return parsed as T;
    }
    return null;
  } catch {
    return null;
  }
};

const parseToolUiPayload = (raw?: string): ToolUiPayload | null => {
  const parsed = safeParseJson<Record<string, unknown>>(raw);
  if (!parsed) {
    return null;
  }
  const ui = parsed.ui;
  if (!ui || typeof ui !== 'object') {
    return null;
  }
  return ui as ToolUiPayload;
};

const formatUiValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '-';
  }
  if (typeof value === 'boolean') {
    return value ? 'yes' : 'no';
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'string') {
    return value || '-';
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

const extractUnifiedDiff = (args: Record<string, unknown>): string => {
  const value = args.unified_diff;
  return typeof value === 'string' ? value : '';
};

const parseUnifiedDiffPreview = (
  unifiedDiff: string,
  maxLines: number = MAX_DIFF_PREVIEW_LINES,
): UnifiedDiffPreview => {
  const sourceLines = unifiedDiff.split(/\r?\n/);
  const lines: DiffPreviewLine[] = [];
  let additions = 0;
  let deletions = 0;
  let hunks = 0;

  for (const line of sourceLines) {
    if (
      line.startsWith('diff ') ||
      line.startsWith('index ') ||
      line.startsWith('--- ') ||
      line.startsWith('+++ ')
    ) {
      lines.push({ type: 'meta', text: line });
      continue;
    }
    if (line.startsWith('@@')) {
      hunks += 1;
      lines.push({ type: 'hunk', text: line });
      continue;
    }
    if (line.startsWith('+') && !line.startsWith('+++')) {
      additions += 1;
      lines.push({ type: 'add', text: line });
      continue;
    }
    if (line.startsWith('-') && !line.startsWith('---')) {
      deletions += 1;
      lines.push({ type: 'remove', text: line });
      continue;
    }
    lines.push({ type: 'context', text: line });
  }

  const hiddenLineCount = lines.length > maxLines ? lines.length - maxLines : 0;
  return {
    lines: hiddenLineCount > 0 ? lines.slice(0, maxLines) : lines,
    additions,
    deletions,
    hunks,
    hiddenLineCount,
  };
};

const diffPreviewLineClass = (type: DiffPreviewLineType): string => {
  if (type === 'meta') return 'text-gray-500 dark:text-gray-400';
  if (type === 'hunk') return 'text-yellow-700 dark:text-yellow-300 bg-yellow-50/70 dark:bg-yellow-900/20';
  if (type === 'add') return 'text-green-700 dark:text-green-300 bg-green-50/80 dark:bg-green-900/20';
  if (type === 'remove') return 'text-red-700 dark:text-red-300 bg-red-50/80 dark:bg-red-900/20';
  return 'text-gray-700 dark:text-gray-300';
};

const extractApplyErrorMessage = (err: unknown): string => {
  if (err && typeof err === 'object') {
    const maybeResponse = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = maybeResponse?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (detail && typeof detail === 'object') {
      const code = (detail as { code?: unknown }).code;
      const message = (detail as { message?: unknown }).message;
      if (typeof code === 'string' && typeof message === 'string') {
        return `${code}: ${message}`;
      }
      if (typeof message === 'string' && message.trim()) {
        return message;
      }
    }
  }
  return err instanceof Error ? err.message : 'Failed to apply diff.';
};

const truncateText = (value: string, maxChars: number): string => {
  if (value.length <= maxChars) {
    return value;
  }
  return `${value.slice(0, Math.max(0, maxChars - 3)).trimEnd()}...`;
};

const developerPayloadBlock = (
  title: string,
  argumentsLabel: string,
  resultLabel: string,
  args: Record<string, unknown>,
  result?: string,
) => (
  <details className="min-w-0 max-w-full rounded border border-gray-200 bg-white/40 p-2 dark:border-gray-700 dark:bg-gray-900/20">
    <summary className="cursor-pointer font-medium text-gray-600 dark:text-gray-400">
      {title}
    </summary>
    <div className="mt-1 min-w-0 space-y-2">
      <div>
        <span className="font-medium text-gray-500 dark:text-gray-400">
          {argumentsLabel}:
        </span>
        <pre className="mt-0.5 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded bg-gray-100 p-1.5 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          {JSON.stringify(args, null, 2)}
        </pre>
      </div>
      {result !== undefined && (
        <div>
          <span className="font-medium text-gray-500 dark:text-gray-400">
            {resultLabel}:
          </span>
          <pre className="mt-0.5 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded bg-gray-100 p-1.5 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
            {result}
          </pre>
        </div>
      )}
    </div>
  </details>
);

const buildToolHeaderText = (
  t: TFunction,
  tc: ToolCallInfo,
  formatArgs: (args: Record<string, unknown>) => string,
  parsedToolUi: ToolUiPayload | null,
): string => {
  if (tc.status === 'calling') {
    return t('toolCall.calling', { name: tc.name });
  }

  if (parsedToolUi) {
    const summary = String(parsedToolUi.summary || '').trim();
    if (summary) {
      return `${tc.name}(${formatArgs(tc.args)}) · ${truncateText(summary, 88)}`;
    }
  }

  return `${tc.name}(${formatArgs(tc.args)})`;
};

interface ToolUiDetailsProps {
  parsedToolUi: ToolUiPayload;
}

const ToolUiDetails = ({ parsedToolUi }: ToolUiDetailsProps) => (
  <div data-name="tool-ui-details" className="space-y-3">
    {parsedToolUi.status === 'error' && parsedToolUi.error_message && (
      <div className="rounded border border-red-200 bg-red-50 p-2 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
        {parsedToolUi.error_message}
      </div>
    )}

    {(parsedToolUi.sections || []).map((section, sectionIndex) => {
      const key = `${section.kind || 'unknown'}-${sectionIndex}`;
      if (section.kind === 'fields') {
        const fields = Array.isArray(section.fields) ? section.fields : [];
        if (fields.length === 0) {
          return null;
        }
        return (
          <div key={key} className="grid gap-2 sm:grid-cols-2">
            {fields.map((field, fieldIndex) => (
              <div
                key={`${key}-field-${fieldIndex}`}
                className="rounded border border-gray-200 bg-white/70 p-2 dark:border-gray-700 dark:bg-gray-900/30"
              >
                <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  {field.label || '-'}
                </div>
                <div className="mt-1 break-words text-gray-800 dark:text-gray-100">
                  {formatUiValue(field.value)}
                </div>
              </div>
            ))}
          </div>
        );
      }

      if (section.kind === 'items') {
        const items = Array.isArray(section.items) ? section.items : [];
        return (
          <div key={key} className="space-y-2">
            {section.title && (
              <div className="font-medium text-gray-700 dark:text-gray-200">
                {section.title}
              </div>
            )}
            {items.length === 0 ? (
              <div className="rounded border border-gray-200 bg-white/70 p-3 text-gray-600 dark:border-gray-700 dark:bg-gray-900/30 dark:text-gray-300">
                {section.empty_message || '-'}
              </div>
            ) : (
              items.map((item, itemIndex) => {
                const itemUrl = String(item.url || '').trim();
                const itemKey = `${key}-item-${itemIndex}`;
                const cardBody = (
                  <>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        {item.subtitle && (
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            {item.subtitle}
                          </div>
                        )}
                        <div className="mt-1 break-words font-medium text-gray-900 dark:text-gray-100">
                          {item.title || '-'}
                        </div>
                        {itemUrl && (
                          <div className="mt-1 break-all text-xs text-sky-700 dark:text-sky-300">
                            {itemUrl}
                          </div>
                        )}
                      </div>
                      {itemUrl && (
                        <ArrowTopRightOnSquareIcon className="h-4 w-4 flex-shrink-0 text-gray-400" />
                      )}
                    </div>
                    {item.description && (
                      <p className="mt-2 whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
                        {item.description}
                      </p>
                    )}
                  </>
                );
                if (itemUrl) {
                  return (
                    <a
                      key={itemKey}
                      href={itemUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="block rounded-lg border border-gray-200 bg-white/80 p-3 transition hover:border-sky-300 hover:bg-white dark:border-gray-700 dark:bg-gray-900/30 dark:hover:border-sky-700"
                    >
                      {cardBody}
                    </a>
                  );
                }
                return (
                  <div
                    key={itemKey}
                    className="rounded-lg border border-gray-200 bg-white/80 p-3 dark:border-gray-700 dark:bg-gray-900/30"
                  >
                    {cardBody}
                  </div>
                );
              })
            )}
          </div>
        );
      }

      if (section.kind === 'text') {
        return (
          <div key={key} className="rounded-lg border border-gray-200 bg-white/80 p-3 dark:border-gray-700 dark:bg-gray-900/30">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="font-medium text-gray-700 dark:text-gray-200">
                {section.title || 'Text'}
              </div>
              {section.truncated && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                  Truncated
                </span>
              )}
            </div>
            <pre className="max-h-72 max-w-full overflow-auto whitespace-pre-wrap break-words text-sm text-gray-700 dark:text-gray-300">
              {section.text || '-'}
            </pre>
          </div>
        );
      }
      return null;
    })}
  </div>
);

interface ApplyDiffDetailsProps {
  applyDiffPreview: UnifiedDiffPreview | null;
  applyError: string;
  applySummaryAdditions: number;
  applySummaryDeletions: number;
  applySummaryHunks: number;
  baseHashArg: string;
  developerModeEnabled: boolean;
  dryRunArg?: boolean;
  parsedResult: ApplyDiffResultPayload | null;
  t: TFunction;
  tc: ToolCallInfo;
}

const ApplyDiffDetails = ({
  applyDiffPreview,
  applyError,
  applySummaryAdditions,
  applySummaryDeletions,
  applySummaryHunks,
  baseHashArg,
  developerModeEnabled,
  dryRunArg,
  parsedResult,
  t,
  tc,
}: ApplyDiffDetailsProps) => (
  <div className="space-y-2">
    <div data-name="tool-apply-diff-preview" className="rounded border border-gray-200 bg-white/70 dark:border-gray-700 dark:bg-gray-900/30">
      <div className="border-b border-gray-200 px-2 py-1 font-medium text-gray-700 dark:border-gray-700 dark:text-gray-200">
        {t('toolCall.applyDiff.diffPreview')}
      </div>
      {applyDiffPreview ? (
        <pre className="max-h-64 max-w-full overflow-auto p-2 text-[11px] font-mono leading-5 whitespace-pre-wrap break-words">
          {applyDiffPreview.lines.map((line, lineIndex) => (
            <div
              key={`${lineIndex}-${line.text}`}
              className={`px-1 rounded ${diffPreviewLineClass(line.type)}`}
            >
              {line.text || ' '}
            </div>
          ))}
          {applyDiffPreview.hiddenLineCount > 0 && (
            <div className="px-1 text-gray-500 dark:text-gray-400">
              {t('toolCall.applyDiff.linesHidden', { count: applyDiffPreview.hiddenLineCount })}
            </div>
          )}
        </pre>
      ) : (
        <div className="p-2 text-gray-500 dark:text-gray-400">
          {t('toolCall.applyDiff.noDiffProvided')}
        </div>
      )}
    </div>

    {parsedResult?.error?.message && (
      <div className="rounded border border-red-200 bg-red-50 p-2 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
        {(parsedResult.error.code || 'ERROR')}: {parsedResult.error.message}
      </div>
    )}

    {applyError && (
      <div className="rounded border border-red-200 bg-red-50 p-2 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
        {applyError}
      </div>
    )}

    {developerModeEnabled && (
      <div className="space-y-1 rounded border border-blue-200 bg-white/70 p-2 dark:border-blue-800 dark:bg-gray-900/30">
        <div className="font-medium text-gray-700 dark:text-gray-200">
          {t('toolCall.applyDiff.request')}
        </div>
        {baseHashArg && (
          <div className="text-gray-700 dark:text-gray-300">
            {t('toolCall.applyDiff.baseHash')}: <code>{baseHashArg}</code>
          </div>
        )}
        {typeof dryRunArg === 'boolean' && (
          <div className="text-gray-700 dark:text-gray-300">
            {t('toolCall.applyDiff.dryRun')}: <code>{String(dryRunArg)}</code>
          </div>
        )}
        <div className="text-gray-700 dark:text-gray-300">
          {t('toolCall.applyDiff.summary', {
            additions: applySummaryAdditions,
            deletions: applySummaryDeletions,
            hunks: applySummaryHunks,
          })}
        </div>
        {parsedResult && (
          <div className="text-gray-700 dark:text-gray-300">
            {t('toolCall.applyDiff.file')}: <code>{parsedResult.file_path || '-'}</code>
          </div>
        )}
      </div>
    )}

    {developerModeEnabled && developerPayloadBlock(
      t('toolCall.applyDiff.rawPayload'),
      t('toolCall.arguments'),
      t('toolCall.result'),
      tc.args,
      tc.result,
    )}
  </div>
);

interface ApplyDiffActionsProps {
  applyError: string;
  applySummaryAdditions: number;
  applySummaryDeletions: number;
  applySummaryHunks: number;
  developerModeEnabled: boolean;
  isApplied: boolean;
  isApplying: boolean;
  onApply: () => void;
  onDiscard: () => void;
  patchExpiryLabel: string;
  parsedResult: ApplyDiffResultPayload | null;
}

const ApplyDiffActions = ({
  applyError,
  applySummaryAdditions,
  applySummaryDeletions,
  applySummaryHunks,
  developerModeEnabled,
  isApplied,
  isApplying,
  onApply,
  onDiscard,
  patchExpiryLabel,
  parsedResult,
}: ApplyDiffActionsProps) => (
  <div data-name="tool-apply-diff-actions" className="space-y-2 rounded border border-green-200 bg-green-50 p-2 dark:border-green-800 dark:bg-green-900/20">
    <div className="font-medium text-green-700 dark:text-green-300">
      Diff preview ready
    </div>
    {developerModeEnabled && (
      <>
        <div className="text-gray-700 dark:text-gray-300">
          {parsedResult?.file_path}
          {' | '}
          +{applySummaryAdditions}
          {' / -'}
          {applySummaryDeletions}
          {' / hunks '}
          {applySummaryHunks}
        </div>
        {patchExpiryLabel && (
          <div className="text-gray-600 dark:text-gray-400">
            Expires at {patchExpiryLabel}
          </div>
        )}
      </>
    )}
    {applyError && (
      <div className="text-red-600 dark:text-red-400">{applyError}</div>
    )}
    <div className="flex gap-2">
      <button
        type="button"
        disabled={isApplying || isApplied}
        onClick={onApply}
        className="rounded bg-green-600 px-2 py-1 text-white disabled:opacity-50"
      >
        {isApplied ? 'Applied' : (isApplying ? 'Applying...' : 'Apply Changes')}
      </button>
      <button
        type="button"
        disabled={isApplying || isApplied}
        onClick={onDiscard}
        className="rounded border border-gray-400 px-2 py-1 text-gray-700 disabled:opacity-50 dark:text-gray-200"
      >
        Discard
      </button>
    </div>
  </div>
);

interface DefaultToolDetailsProps {
  t: TFunction;
  tc: ToolCallInfo;
}

const DefaultToolDetails = ({ t, tc }: DefaultToolDetailsProps) => (
  <div className="space-y-2">
    {Object.keys(tc.args).length > 0 && (
      <div>
        <span className="font-medium text-gray-500 dark:text-gray-400">
          {t('toolCall.arguments')}:
        </span>
        <pre className="mt-0.5 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded bg-gray-100 p-1.5 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          {JSON.stringify(tc.args, null, 2)}
        </pre>
      </div>
    )}

    {tc.result !== undefined && (
      <div>
        <span className="font-medium text-gray-500 dark:text-gray-400">
          {t('toolCall.result')}:
        </span>
        <pre className="mt-0.5 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded bg-gray-100 p-1.5 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          {tc.result}
        </pre>
      </div>
    )}
  </div>
);

interface ToolCallItemProps {
  applyErrors: Record<string, string>;
  appliedPatchIds: Record<string, boolean>;
  applyingPatchIds: Record<string, boolean>;
  developerModeEnabled: boolean;
  dismissedPatchIds: Record<string, boolean>;
  expandedIndex: number | null;
  formatArgs: (args: Record<string, unknown>) => string;
  handleApplyPatch: (patchId: string, payload: ApplyDiffResultPayload) => void;
  handleDiscardPatch: (patchId: string) => void;
  index: number;
  t: TFunction;
  tc: ToolCallInfo;
  toggleExpand: (index: number) => void;
}

const ToolCallItem = ({
  applyErrors,
  appliedPatchIds,
  applyingPatchIds,
  developerModeEnabled,
  dismissedPatchIds,
  expandedIndex,
  formatArgs,
  handleApplyPatch,
  handleDiscardPatch,
  index,
  t,
  tc,
  toggleExpand,
}: ToolCallItemProps) => {
  const isExpanded = expandedIndex === index;
  const isCalling = tc.status === 'calling';
  const isError = tc.status === 'error';
  const isApplyDiffTool = APPLY_DIFF_TOOL_NAMES.has(tc.name);
  const parsedResult = isApplyDiffTool ? safeParseJson<ApplyDiffResultPayload>(tc.result) : null;
  const parsedToolUi = parseToolUiPayload(tc.result);
  const applyDiffRaw = isApplyDiffTool ? extractUnifiedDiff(tc.args) : '';
  const applyDiffPreview = applyDiffRaw ? parseUnifiedDiffPreview(applyDiffRaw) : null;
  const patchId = parsedResult?.pending_patch_id || '';
  const patchExpiryLabel = typeof parsedResult?.pending_patch_expires_at === 'number'
    ? new Date(parsedResult.pending_patch_expires_at).toLocaleTimeString()
    : '';
  const isDryRunApplyDiff = Boolean(
    parsedResult &&
    parsedResult.ok &&
    parsedResult.mode === 'dry_run' &&
    patchId &&
    !dismissedPatchIds[patchId]
  );
  const isApplying = patchId ? Boolean(applyingPatchIds[patchId]) : false;
  const isApplied = patchId ? Boolean(appliedPatchIds[patchId]) : false;
  const applyError = patchId ? applyErrors[patchId] : '';
  const applySummaryAdditions = parsedResult?.preview?.additions ?? applyDiffPreview?.additions ?? 0;
  const applySummaryDeletions = parsedResult?.preview?.deletions ?? applyDiffPreview?.deletions ?? 0;
  const applySummaryHunks = parsedResult?.preview?.hunks ?? applyDiffPreview?.hunks ?? 0;
  const baseHashArg = typeof tc.args.base_hash === 'string' ? tc.args.base_hash : '';
  const dryRunArg = typeof tc.args.dry_run === 'boolean' ? tc.args.dry_run : undefined;
  const statusIcon = isCalling ? (
    <WrenchScrewdriverIcon className="h-4 w-4 animate-spin" />
  ) : isError ? (
    <ExclamationCircleIcon className="h-4 w-4 text-red-500" />
  ) : (
    <CheckCircleIcon className="h-4 w-4 text-green-500 dark:text-green-400" />
  );
  const headerText = buildToolHeaderText(t, tc, formatArgs, parsedToolUi);

  return (
    <div
      data-name="tool-call-item"
      className="min-w-0 max-w-full overflow-hidden rounded-lg border border-gray-200 bg-gray-50/70 text-sm dark:border-gray-700 dark:bg-gray-900/20"
    >
      <button
        type="button"
        onClick={() => toggleExpand(index)}
        className="flex w-full min-w-0 items-center gap-2 px-3 py-2 text-left hover:bg-gray-100/80 dark:hover:bg-gray-800/30"
      >
        <span className="flex-shrink-0">{statusIcon}</span>
        <span className="min-w-0 flex-1 truncate font-mono text-xs text-gray-800 dark:text-gray-200">
          {headerText}
        </span>
        <ChevronDownIcon
          className={`h-4 w-4 flex-shrink-0 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
        />
      </button>

      {isExpanded && (
        <div className="min-w-0 max-w-full space-y-2 border-t border-gray-200 px-3 py-2 dark:border-gray-700">
          {isApplyDiffTool ? (
            <ApplyDiffDetails
              applyDiffPreview={applyDiffPreview}
              applyError={applyError}
              applySummaryAdditions={applySummaryAdditions}
              applySummaryDeletions={applySummaryDeletions}
              applySummaryHunks={applySummaryHunks}
              baseHashArg={baseHashArg}
              developerModeEnabled={developerModeEnabled}
              dryRunArg={dryRunArg}
              parsedResult={parsedResult}
              t={t}
              tc={tc}
            />
          ) : parsedToolUi ? (
            <ToolUiDetails parsedToolUi={parsedToolUi} />
          ) : (
            <DefaultToolDetails t={t} tc={tc} />
          )}

          {!isApplyDiffTool && developerModeEnabled && developerPayloadBlock(
            t('toolCall.rawPayload'),
            t('toolCall.arguments'),
            t('toolCall.result'),
            tc.args,
            tc.result,
          )}

          {isDryRunApplyDiff && parsedResult && patchId && (
            <ApplyDiffActions
              applyError={applyError}
              applySummaryAdditions={applySummaryAdditions}
              applySummaryDeletions={applySummaryDeletions}
              applySummaryHunks={applySummaryHunks}
              developerModeEnabled={developerModeEnabled}
              isApplied={isApplied}
              isApplying={isApplying}
              onApply={() => handleApplyPatch(patchId, parsedResult)}
              onDiscard={() => handleDiscardPatch(patchId)}
              patchExpiryLabel={patchExpiryLabel}
              parsedResult={parsedResult}
            />
          )}
        </div>
      )}
    </div>
  );
};

export const ToolCallBlock: React.FC<ToolCallBlockProps> = ({ toolCalls, sessionId }) => {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [applyingPatchIds, setApplyingPatchIds] = useState<Record<string, boolean>>({});
  const [appliedPatchIds, setAppliedPatchIds] = useState<Record<string, boolean>>(
    () => readPatchFlags(APPLIED_PATCH_STORAGE_KEY),
  );
  const [dismissedPatchIds, setDismissedPatchIds] = useState<Record<string, boolean>>(
    () => readPatchFlags(DISMISSED_PATCH_STORAGE_KEY),
  );
  const [applyErrors, setApplyErrors] = useState<Record<string, string>>({});
  const autoExpandedPatchIdsRef = useRef<Record<string, boolean>>({});
  const { t } = useTranslation('chat');
  const { enabled: developerModeEnabled } = useDeveloperMode();
  const location = useLocation();
  const projectId = useMemo(() => parseProjectIdFromPath(location.pathname), [location.pathname]);

  const toggleExpand = (index: number) => {
    setExpandedIndex(prev => (prev === index ? null : index));
  };

  useEffect(() => {
    if (!toolCalls || toolCalls.length === 0) {
      return;
    }
    for (let index = toolCalls.length - 1; index >= 0; index -= 1) {
      const tc = toolCalls[index];
      if (!APPLY_DIFF_TOOL_NAMES.has(tc.name)) {
        continue;
      }
      const parsedResult = safeParseJson<ApplyDiffResultPayload>(tc.result);
      const patchId = parsedResult?.pending_patch_id;
      if (
        patchId &&
        parsedResult?.ok &&
        parsedResult?.mode === 'dry_run' &&
        !dismissedPatchIds[patchId] &&
        !appliedPatchIds[patchId] &&
        !autoExpandedPatchIdsRef.current[patchId]
      ) {
        autoExpandedPatchIdsRef.current[patchId] = true;
        setExpandedIndex(index);
        break;
      }
    }
  }, [toolCalls, dismissedPatchIds, appliedPatchIds]);

  useEffect(() => {
    writePatchFlags(APPLIED_PATCH_STORAGE_KEY, appliedPatchIds);
  }, [appliedPatchIds]);

  useEffect(() => {
    writePatchFlags(DISMISSED_PATCH_STORAGE_KEY, dismissedPatchIds);
  }, [dismissedPatchIds]);

  if (!toolCalls || toolCalls.length === 0) return null;

  const formatArgs = (args: Record<string, unknown>): string => {
    const entries = Object.entries(args);
    if (entries.length === 0) return '';
    const summarizeArg = (key: string, value: unknown): string => {
      if (key === 'unified_diff' && typeof value === 'string') {
        return `${key}=<diff ${value.length} chars>`;
      }
      if (typeof value === 'string') {
        if (value.length > 120) {
          return `${key}=${JSON.stringify(`${value.slice(0, 117)}...`)}`;
        }
        return `${key}=${JSON.stringify(value)}`;
      }
      const raw = JSON.stringify(value);
      if (raw.length > 120) {
        return `${key}=${raw.slice(0, 117)}...`;
      }
      return `${key}=${raw}`;
    };
    return entries.map(([key, value]) => summarizeArg(key, value)).join(', ');
  };

  const handleApplyPatch = async (
    patchId: string,
    payload: ApplyDiffResultPayload,
  ) => {
    if (!projectId || !sessionId) {
      setApplyErrors(prev => ({ ...prev, [patchId]: 'Missing project/session context for apply.' }));
      return;
    }
    setApplyingPatchIds(prev => ({ ...prev, [patchId]: true }));
    setApplyErrors(prev => ({ ...prev, [patchId]: '' }));
    try {
      await applyProjectChatDiff(projectId, {
        session_id: sessionId,
        pending_patch_id: patchId,
        expected_hash: payload.base_hash,
      });
      setAppliedPatchIds(prev => ({ ...prev, [patchId]: true }));
      window.dispatchEvent(new CustomEvent('project-file-updated'));
    } catch (err) {
      const msg = extractApplyErrorMessage(err);
      setApplyErrors(prev => ({ ...prev, [patchId]: msg }));
    } finally {
      setApplyingPatchIds(prev => ({ ...prev, [patchId]: false }));
    }
  };

  const handleDiscardPatch = (patchId: string) => {
    setDismissedPatchIds(prev => ({ ...prev, [patchId]: true }));
    setApplyErrors(prev => ({ ...prev, [patchId]: '' }));
  };

  return (
    <div data-name="tool-call-block" className="mb-3 w-full min-w-0 max-w-full space-y-1.5">
      {toolCalls.map((tc, index) => {
        return (
          <ToolCallItem
            key={`${tc.toolCallId || tc.name}-${index}`}
            applyErrors={applyErrors}
            appliedPatchIds={appliedPatchIds}
            applyingPatchIds={applyingPatchIds}
            developerModeEnabled={developerModeEnabled}
            dismissedPatchIds={dismissedPatchIds}
            expandedIndex={expandedIndex}
            formatArgs={formatArgs}
            handleApplyPatch={handleApplyPatch}
            handleDiscardPatch={handleDiscardPatch}
            index={index}
            t={t}
            tc={tc}
            toggleExpand={toggleExpand}
          />
        );
      })}
    </div>
  );
};
