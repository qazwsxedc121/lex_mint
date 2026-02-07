/**
 * ContextUsageBar - Compact progress bar showing LLM context window usage
 */

import React from 'react';

interface ContextUsageBarProps {
  promptTokens: number | null;
  contextBudget: number | null;
  contextWindow: number | null;
}

function formatNumber(n: number): string {
  return n.toLocaleString();
}

export const ContextUsageBar: React.FC<ContextUsageBarProps> = ({
  promptTokens,
  contextBudget,
  contextWindow,
}) => {
  if (promptTokens == null || contextBudget == null || contextBudget <= 0) {
    return null;
  }

  const percentage = Math.min((promptTokens / contextBudget) * 100, 100);

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
          Context: {formatNumber(promptTokens)} / {formatNumber(contextBudget)} ({percentage.toFixed(0)}%)
        </span>
      </div>
    </div>
  );
};
