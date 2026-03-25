/**
 * TranslationBlock component - displays translated content.
 * Features: collapsible, streaming support, markdown rendering, copy and dismiss buttons.
 */

import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import {
  ChevronDownIcon,
  LanguageIcon,
  ClipboardDocumentIcon,
  ClipboardDocumentCheckIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { normalizeMathDelimiters } from '../utils/markdownMath';

interface TranslationBlockProps {
  translatedText: string;
  isTranslating: boolean;
  onDismiss: () => void;
}

export const TranslationBlock: React.FC<TranslationBlockProps> = ({
  translatedText,
  isTranslating,
  onDismiss,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [isCopied, setIsCopied] = useState(false);

  const headerText = isTranslating ? 'Translating...' : 'Translation';
  const normalizedTranslatedText = useMemo(() => normalizeMathDelimiters(translatedText), [translatedText]);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(translatedText);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch {
      // Fallback: do nothing
    }
  };

  const handleDismiss = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDismiss();
  };

  return (
    <div
      data-name="translation-block"
      className="mt-3 w-full min-w-0 max-w-full rounded-lg border border-teal-200 dark:border-teal-800 overflow-hidden"
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full min-w-0 items-center gap-2 bg-teal-50 px-3 py-2 text-xs font-medium text-teal-700 transition-colors hover:bg-teal-100 dark:bg-teal-900/30 dark:text-teal-300 dark:hover:bg-teal-900/50"
      >
        <span className={`w-4 h-4 transition-transform duration-200 ${isExpanded ? 'rotate-0' : '-rotate-90'}`}>
          <ChevronDownIcon className="w-4 h-4" />
        </span>
        <LanguageIcon className={`w-4 h-4 ${isTranslating ? 'animate-pulse' : ''}`} />
        <span className="min-w-0 flex-1 truncate text-left">{headerText}</span>
        <span className="ml-auto flex flex-shrink-0 items-center gap-1">
          {/* Copy button */}
          {!isTranslating && translatedText && (
            isCopied ? (
              <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-500" />
            ) : (
              <ClipboardDocumentIcon
                className="w-4 h-4 text-teal-500 dark:text-teal-400 hover:text-teal-700 dark:hover:text-teal-200"
                onClick={handleCopy}
              />
            )
          )}
          {/* Dismiss button */}
          <XMarkIcon
            className="w-4 h-4 text-teal-500 dark:text-teal-400 hover:text-teal-700 dark:hover:text-teal-200"
            onClick={handleDismiss}
          />
        </span>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="min-w-0 max-w-full overflow-x-auto overflow-y-auto bg-teal-50/50 px-3 py-2 text-sm text-gray-700 dark:bg-teal-900/20 dark:text-gray-300 max-h-96 break-words [overflow-wrap:anywhere] prose prose-sm dark:prose-invert max-w-none [&_a]:break-all [&_code]:break-words [&_li]:break-words [&_p]:break-words [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_pre]:whitespace-pre-wrap">
          {translatedText ? (
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
              {normalizedTranslatedText}
            </ReactMarkdown>
          ) : isTranslating ? (
            <span className="text-xs text-teal-500 dark:text-teal-400 animate-pulse">Translating...</span>
          ) : null}
        </div>
      )}
    </div>
  );
};
