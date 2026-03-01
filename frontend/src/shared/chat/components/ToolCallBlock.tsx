/**
 * ToolCallBlock component - displays tool/function call info inline.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  ChevronDownIcon,
  WrenchScrewdriverIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import type { ToolCallInfo } from '../../../types/message';
import { useTranslation } from 'react-i18next';
import { applyProjectChatDiff } from '../../../services/api';
import { useDeveloperMode } from '../../../hooks/useDeveloperMode';

interface ToolCallBlockProps {
  toolCalls: ToolCallInfo[];
  sessionId?: string;
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
  error?: {
    code?: string;
    message?: string;
  };
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

const safeParseJson = (raw?: string): ApplyDiffResultPayload | null => {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') {
      return parsed as ApplyDiffResultPayload;
    }
    return null;
  } catch {
    return null;
  }
};

const extractUnifiedDiff = (args: Record<string, unknown>): string => {
  const value = args.unified_diff;
  return typeof value === 'string' ? value : '';
};

const parseUnifiedDiffPreview = (
  unifiedDiff: string,
  maxLines: number = MAX_DIFF_PREVIEW_LINES
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

export const ToolCallBlock: React.FC<ToolCallBlockProps> = ({ toolCalls, sessionId }) => {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [applyingPatchIds, setApplyingPatchIds] = useState<Record<string, boolean>>({});
  const [appliedPatchIds, setAppliedPatchIds] = useState<Record<string, boolean>>(
    () => readPatchFlags(APPLIED_PATCH_STORAGE_KEY)
  );
  const [dismissedPatchIds, setDismissedPatchIds] = useState<Record<string, boolean>>(
    () => readPatchFlags(DISMISSED_PATCH_STORAGE_KEY)
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
      const parsedResult = safeParseJson(tc.result);
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
    return entries.map(([k, v]) => summarizeArg(k, v)).join(', ');
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
    <div data-name="tool-call-block" className="mb-3 space-y-1.5">
      {toolCalls.map((tc, index) => {
        const isExpanded = expandedIndex === index;
        const isCalling = tc.status === 'calling';
        const isError = tc.status === 'error';
        const isApplyDiffTool = APPLY_DIFF_TOOL_NAMES.has(tc.name);
        const parsedResult = isApplyDiffTool ? safeParseJson(tc.result) : null;
        const applyDiffRaw = isApplyDiffTool ? extractUnifiedDiff(tc.args) : '';
        const applyDiffPreview = applyDiffRaw ? parseUnifiedDiffPreview(applyDiffRaw) : null;
        const patchId = parsedResult?.pending_patch_id || '';
        const patchExpiresAt = parsedResult?.pending_patch_expires_at;
        const patchExpiryLabel = typeof patchExpiresAt === 'number'
          ? new Date(patchExpiresAt).toLocaleTimeString()
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
          <WrenchScrewdriverIcon className="w-4 h-4 animate-spin" />
        ) : isError ? (
          <ExclamationCircleIcon className="w-4 h-4 text-red-500" />
        ) : (
          <CheckCircleIcon className="w-4 h-4 text-green-500 dark:text-green-400" />
        );

        const headerText = isCalling
          ? t('toolCall.calling', { name: tc.name })
          : `${tc.name}(${formatArgs(tc.args)})`;

        return (
          <div
            key={`${tc.toolCallId || tc.name}-${index}`}
            className="border border-blue-200 dark:border-blue-800 rounded-lg overflow-hidden"
          >
            <button
              onClick={() => toggleExpand(index)}
              className="w-full flex items-center gap-2 px-3 py-1.5 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-medium hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
            >
              <span className={`w-4 h-4 transition-transform duration-200 ${isExpanded ? 'rotate-0' : '-rotate-90'}`}>
                <ChevronDownIcon className="w-4 h-4" />
              </span>
              {statusIcon}
              <span className="truncate">{headerText}</span>
            </button>

            {isExpanded && (
              <div className="px-3 py-2 bg-blue-50/50 dark:bg-blue-900/20 text-xs space-y-2">
                {!isApplyDiffTool && Object.keys(tc.args).length > 0 && (
                  <div>
                    <span className="font-medium text-gray-500 dark:text-gray-400">
                      {t('toolCall.arguments')}:
                    </span>
                    <pre className="mt-0.5 p-1.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-700 dark:text-gray-300 overflow-x-auto">
                      {JSON.stringify(tc.args, null, 2)}
                    </pre>
                  </div>
                )}

                {!isApplyDiffTool && tc.result !== undefined && (
                  <div>
                    <span className="font-medium text-gray-500 dark:text-gray-400">
                      {t('toolCall.result')}:
                    </span>
                    <pre className="mt-0.5 p-1.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-700 dark:text-gray-300 overflow-x-auto whitespace-pre-wrap">
                      {tc.result}
                    </pre>
                  </div>
                )}

                {isApplyDiffTool && (
                  <div className="space-y-2">
                    <div data-name="tool-apply-diff-preview" className="rounded border border-gray-200 dark:border-gray-700 bg-white/70 dark:bg-gray-900/30">
                      <div className="px-2 py-1 border-b border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-200">
                        {t('toolCall.applyDiff.diffPreview')}
                      </div>
                      {applyDiffPreview ? (
                        <pre className="max-h-64 overflow-auto p-2 text-[11px] leading-5 font-mono whitespace-pre-wrap break-words">
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
                      <div className="rounded border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-2 text-red-700 dark:text-red-300">
                        {(parsedResult.error.code || 'ERROR')}: {parsedResult.error.message}
                      </div>
                    )}

                    {developerModeEnabled && (
                      <div className="rounded border border-blue-200 dark:border-blue-800 bg-white/70 dark:bg-gray-900/30 p-2 space-y-1">
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

                    {developerModeEnabled && (
                      <details className="rounded border border-gray-200 dark:border-gray-700 bg-white/40 dark:bg-gray-900/20 p-2">
                        <summary className="cursor-pointer font-medium text-gray-600 dark:text-gray-400">
                          {t('toolCall.applyDiff.rawPayload')}
                        </summary>
                        <div className="mt-1 space-y-2">
                          <div>
                            <span className="font-medium text-gray-500 dark:text-gray-400">
                              {t('toolCall.arguments')}:
                            </span>
                            <pre className="mt-0.5 p-1.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-700 dark:text-gray-300 overflow-x-auto">
                              {JSON.stringify(tc.args, null, 2)}
                            </pre>
                          </div>
                          {tc.result !== undefined && (
                            <div>
                              <span className="font-medium text-gray-500 dark:text-gray-400">
                                {t('toolCall.result')}:
                              </span>
                              <pre className="mt-0.5 p-1.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-700 dark:text-gray-300 overflow-x-auto whitespace-pre-wrap">
                                {tc.result}
                              </pre>
                            </div>
                          )}
                        </div>
                      </details>
                    )}
                  </div>
                )}

                {isDryRunApplyDiff && (
                  <div data-name="tool-apply-diff-actions" className="rounded border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-2 space-y-2">
                    <div className="text-green-700 dark:text-green-300 font-medium">
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
                        onClick={() => handleApplyPatch(patchId, parsedResult!)}
                        className="px-2 py-1 rounded bg-green-600 text-white disabled:opacity-50"
                      >
                        {isApplied ? 'Applied' : (isApplying ? 'Applying...' : 'Apply Changes')}
                      </button>
                      <button
                        type="button"
                        disabled={isApplying || isApplied}
                        onClick={() => handleDiscardPatch(patchId)}
                        className="px-2 py-1 rounded border border-gray-400 text-gray-700 dark:text-gray-200 disabled:opacity-50"
                      >
                        Discard
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
