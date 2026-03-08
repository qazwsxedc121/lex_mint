/**
 * ContextUsageBar - Compact progress bar showing LLM context window usage
 */

import React from 'react';
import type { ContextInfo } from '../../../types/message';

interface ContextUsageBarProps {
  promptTokens: number | null;
  contextInfo: ContextInfo | null;
}

function formatNumber(n: number): string {
  return n.toLocaleString();
}

export const ContextUsageBar: React.FC<ContextUsageBarProps> = ({
  promptTokens,
  contextInfo,
}) => {
  const contextBudget = contextInfo?.context_budget ?? null;
  const contextWindow = contextInfo?.context_window ?? null;
  const effectivePromptTokens = promptTokens ?? contextInfo?.estimated_prompt_tokens ?? null;

  if (effectivePromptTokens == null || contextBudget == null || contextBudget <= 0) {
    return null;
  }

  const percentage = Math.min((effectivePromptTokens / contextBudget) * 100, 100);
  const contextLabel = contextWindow && contextWindow > 0
    ? `${formatNumber(contextBudget)} / ${formatNumber(contextWindow)}`
    : formatNumber(contextBudget);
  const segmentReports = contextInfo?.segments ?? [];

  // Color: green < 50%, yellow 50-75%, red > 75%
  let barColor: string;
  let textColor: string;
  if (percentage < 50) {
    barColor = 'bg-green-500';
    textColor = 'text-green-700 dark:text-green-400';
  } else if (percentage < 75) {
    barColor = 'bg-yellow-500';
    textColor = 'text-yellow-700 dark:text-yellow-400';
  } else {
    barColor = 'bg-red-500';
    textColor = 'text-red-700 dark:text-red-400';
  }

  return (
    <div data-name="context-usage-bar" className="px-4 py-1">
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full ${barColor} rounded-full transition-all duration-300`}
            style={{ width: `${percentage}%` }}
          />
        </div>
        <span className={`text-xs whitespace-nowrap ${textColor}`}>
          Context: {formatNumber(effectivePromptTokens)} / {contextLabel} ({percentage.toFixed(0)}%)
        </span>
      </div>
      {segmentReports.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5" data-name="context-usage-segments">
          {segmentReports.map((segment) => {
            const stateLabel = !segment.included
              ? (segment.drop_reason || 'dropped')
              : segment.truncated
                ? 'trimmed'
                : 'kept';
            const chipClassName = !segment.included
              ? 'border-gray-300 text-gray-500 dark:border-gray-700 dark:text-gray-400'
              : segment.truncated
                ? 'border-yellow-300 text-yellow-700 dark:border-yellow-700 dark:text-yellow-300'
                : 'border-green-300 text-green-700 dark:border-green-700 dark:text-green-300';
            return (
              <span
                key={segment.name}
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${chipClassName}`}
              >
                <span className="font-medium">{segment.name}</span>
                <span>{formatNumber(segment.estimated_tokens_after)}</span>
                <span className="opacity-75">{stateLabel}</span>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
};
