/**
 * CompareResponseView - Displays multiple model responses side-by-side or in tabs.
 */

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import type { CompareModelResponse } from '../../../types/message';
import { CodeBlock } from './CodeBlock';
import { MermaidBlock } from './MermaidBlock';
import { normalizeMathDelimiters } from '../utils/markdownMath';

interface CompareResponseViewProps {
  responses: CompareModelResponse[];
  isStreaming: boolean;
}

const VIEW_MODE_KEY = 'lex-mint.compare-view-mode';

const markdownComponents = {
  code({ className, children, ...props }: any) {
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';
    const value = String(children).replace(/\n$/, '');
    const isInline = !className;

    return !isInline && language ? (
      language === 'mermaid'
        ? <MermaidBlock value={value} />
        : <CodeBlock language={language} value={value} />
    ) : (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  table({ children }: any) {
    return (
      <div className="overflow-x-auto my-4">
        <table className="min-w-full divide-y divide-gray-300 dark:divide-gray-600">
          {children}
        </table>
      </div>
    );
  },
};

export const CompareResponseView: React.FC<CompareResponseViewProps> = ({
  responses,
  isStreaming,
}) => {
  const { t } = useTranslation('chat');
  const [viewMode, setViewMode] = useState<'side-by-side' | 'tabs'>(() => {
    try {
      const stored = localStorage.getItem(VIEW_MODE_KEY);
      return stored === 'tabs' ? 'tabs' : 'side-by-side';
    } catch {
      return 'side-by-side';
    }
  });
  const [activeTab, setActiveTab] = useState(0);

  const toggleViewMode = () => {
    const next = viewMode === 'side-by-side' ? 'tabs' : 'side-by-side';
    setViewMode(next);
    try {
      localStorage.setItem(VIEW_MODE_KEY, next);
    } catch {
      // Ignore localStorage write failures.
    }
  };

  const gridCols = responses.length <= 2 ? 'grid-cols-2' : 'grid-cols-3';

  const renderResponsePanel = (response: CompareModelResponse) => {
    const isEmpty = !response.content && !response.error;
    const isGenerating = isStreaming && isEmpty;

    return (
      <div key={response.model_id} className="flex flex-col min-w-0">
        {/* Model name badge */}
        <div className="flex items-center gap-2 mb-2">
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 truncate">
            {response.model_name || response.model_id}
          </span>
          {response.usage && (
            <span className="text-[10px] text-gray-400 dark:text-gray-500">
              {response.usage.total_tokens}t
            </span>
          )}
          {response.cost && (
            <span className="text-[10px] text-gray-400 dark:text-gray-500">
              ${response.cost.total_cost.toFixed(4)}
            </span>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-auto">
          {response.error ? (
            <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded p-2">
              {t('compare.modelError', { error: response.error })}
            </div>
          ) : isGenerating ? (
            <div className="text-sm text-gray-400 dark:text-gray-500 animate-pulse">
              {t('compare.generating')}
            </div>
          ) : (
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={markdownComponents}
              >
                {normalizeMathDelimiters(response.content)}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div data-name="compare-response-view" className="w-full">
      {/* View mode toggle */}
      <div className="flex justify-end mb-2">
        <button
          type="button"
          onClick={toggleViewMode}
          className="text-xs px-2 py-1 rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          {viewMode === 'side-by-side' ? t('compare.tabs') : t('compare.sideBySide')}
        </button>
      </div>

      {viewMode === 'side-by-side' ? (
        /* Side-by-side layout */
        <div className={`grid ${gridCols} gap-4`}>
          {responses.map((response) => (
            <div
              key={response.model_id}
              className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 bg-white dark:bg-gray-800/50"
            >
              {renderResponsePanel(response)}
            </div>
          ))}
        </div>
      ) : (
        /* Tabs layout */
        <div>
          <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700 mb-3">
            {responses.map((response, index) => (
              <button
                key={response.model_id}
                type="button"
                onClick={() => setActiveTab(index)}
                className={`px-3 py-1.5 text-sm transition-colors ${
                  activeTab === index
                    ? 'text-purple-700 dark:text-purple-300 border-b-2 border-purple-500'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                {response.model_name || response.model_id}
                {response.error && ' (!)'}
              </button>
            ))}
          </div>
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 bg-white dark:bg-gray-800/50">
            {responses[activeTab] && renderResponsePanel(responses[activeTab])}
          </div>
        </div>
      )}
    </div>
  );
};
