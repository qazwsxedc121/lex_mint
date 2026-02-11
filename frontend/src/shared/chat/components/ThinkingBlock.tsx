/**
 * ThinkingBlock component - displays AI thinking/reasoning content.
 * Features: live timer, content preview while collapsed, markdown rendering, copy button.
 */

import React, { useState, useEffect, useRef, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import {
  ChevronDownIcon,
  LightBulbIcon,
  ClipboardDocumentIcon,
  ClipboardDocumentCheckIcon,
} from '@heroicons/react/24/outline';
import { normalizeMathDelimiters } from '../utils/markdownMath';

interface ThinkingBlockProps {
  thinking: string;
  isThinkingInProgress: boolean;
  thinkingDurationMs?: number;
}

export const ThinkingBlock: React.FC<ThinkingBlockProps> = ({
  thinking,
  isThinkingInProgress,
  thinkingDurationMs,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const startTimeRef = useRef<number | null>(null);
  const previewRef = useRef<HTMLDivElement>(null);

  // Live timer during streaming
  useEffect(() => {
    if (isThinkingInProgress) {
      if (!startTimeRef.current) {
        startTimeRef.current = Date.now();
      }
      const interval = setInterval(() => {
        setElapsedMs(Date.now() - startTimeRef.current!);
      }, 100);
      return () => clearInterval(interval);
    } else {
      // Reset for next thinking session
      startTimeRef.current = null;
    }
  }, [isThinkingInProgress]);

  // Auto-scroll preview to bottom during streaming
  useEffect(() => {
    if (isThinkingInProgress && previewRef.current) {
      previewRef.current.scrollTop = previewRef.current.scrollHeight;
    }
  }, [thinking, isThinkingInProgress]);

  // Format duration as "X.Xs"
  const formatDuration = (ms: number): string => {
    return (ms / 1000).toFixed(1) + 's';
  };

  // Get the last 3 lines for preview
  const previewLines = useMemo(() => {
    const lines = thinking.split('\n').filter(l => l.trim());
    return lines.slice(-3);
  }, [thinking]);

  const normalizedThinking = useMemo(() => normalizeMathDelimiters(thinking), [thinking]);

  const displayDuration = isThinkingInProgress
    ? formatDuration(elapsedMs)
    : thinkingDurationMs !== undefined
      ? formatDuration(thinkingDurationMs)
      : null;

  const headerText = isThinkingInProgress
    ? `Thinking... ${displayDuration || ''}`
    : `Thought for ${displayDuration || `${thinking.length} chars`}`;

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(thinking);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch {
      // Fallback: do nothing
    }
  };

  const isOpen = isExpanded;

  return (
    <div data-name="thinking-block" className="mb-3 border border-amber-200 dark:border-amber-800 rounded-lg overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-xs font-medium hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors"
      >
        <span className={`w-4 h-4 transition-transform duration-200 ${isOpen ? 'rotate-0' : '-rotate-90'}`}>
          <ChevronDownIcon className="w-4 h-4" />
        </span>
        <LightBulbIcon className={`w-4 h-4 ${isThinkingInProgress ? 'animate-pulse' : ''}`} />
        <span>{headerText}</span>
        {/* Copy button (only when completed and expanded) */}
        {!isThinkingInProgress && isOpen && (
          <span className="ml-auto">
            {isCopied ? (
              <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-500" />
            ) : (
              <ClipboardDocumentIcon
                className="w-4 h-4 text-amber-500 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-200"
                onClick={handleCopy}
              />
            )}
          </span>
        )}
      </button>

      {/* Content preview while collapsed + streaming */}
      {!isOpen && isThinkingInProgress && previewLines.length > 0 && (
        <div
          ref={previewRef}
          className="relative px-3 py-1.5 bg-amber-50/50 dark:bg-amber-900/20 overflow-hidden"
          style={{ maxHeight: '42px' }}
        >
          <div
            className="dark:hidden absolute inset-0 pointer-events-none z-10"
            style={{
              background: 'linear-gradient(to bottom, rgba(255,251,235,0.9) 0%, transparent 100%)',
            }}
          />
          <div
            className="hidden dark:block absolute inset-0 pointer-events-none z-10"
            style={{
              background: 'linear-gradient(to bottom, rgba(120,53,15,0.3) 0%, transparent 100%)',
            }}
          />
          {previewLines.map((line, i) => (
            <div key={i} className="text-[11px] leading-[14px] text-gray-500 dark:text-gray-400 truncate">
              {line}
            </div>
          ))}
        </div>
      )}

      {/* Expanded content */}
      {isOpen && (
        <div className="px-3 py-2 bg-amber-50/50 dark:bg-amber-900/20 text-xs text-gray-600 dark:text-gray-400 max-h-64 overflow-y-auto prose prose-xs dark:prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-pre:my-1">
          <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
            {normalizedThinking}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
};
