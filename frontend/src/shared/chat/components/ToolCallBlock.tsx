/**
 * ToolCallBlock component - displays tool/function call info inline.
 * Similar pattern to ThinkingBlock: collapsible, shows status during streaming.
 */

import React, { useState } from 'react';
import {
  ChevronDownIcon,
  WrenchScrewdriverIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import type { ToolCallInfo } from '../../../types/message';
import { useTranslation } from 'react-i18next';

interface ToolCallBlockProps {
  toolCalls: ToolCallInfo[];
}

export const ToolCallBlock: React.FC<ToolCallBlockProps> = ({ toolCalls }) => {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const { t } = useTranslation('chat');

  if (!toolCalls || toolCalls.length === 0) return null;

  const toggleExpand = (index: number) => {
    setExpandedIndex(prev => (prev === index ? null : index));
  };

  const formatArgs = (args: Record<string, unknown>): string => {
    const entries = Object.entries(args);
    if (entries.length === 0) return '';
    return entries.map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ');
  };

  return (
    <div data-name="tool-call-block" className="mb-3 space-y-1.5">
      {toolCalls.map((tc, index) => {
        const isExpanded = expandedIndex === index;
        const isCalling = tc.status === 'calling';
        const isError = tc.status === 'error';

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
            key={index}
            className="border border-blue-200 dark:border-blue-800 rounded-lg overflow-hidden"
          >
            {/* Header */}
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

            {/* Expanded details */}
            {isExpanded && (
              <div className="px-3 py-2 bg-blue-50/50 dark:bg-blue-900/20 text-xs space-y-1.5">
                {/* Arguments */}
                {Object.keys(tc.args).length > 0 && (
                  <div>
                    <span className="font-medium text-gray-500 dark:text-gray-400">
                      {t('toolCall.arguments')}:
                    </span>
                    <pre className="mt-0.5 p-1.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-700 dark:text-gray-300 overflow-x-auto">
                      {JSON.stringify(tc.args, null, 2)}
                    </pre>
                  </div>
                )}
                {/* Result */}
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
            )}
          </div>
        );
      })}
    </div>
  );
};
