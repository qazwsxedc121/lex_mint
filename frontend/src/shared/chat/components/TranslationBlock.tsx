/**
 * TranslationBlock component - displays translated content.
 * Features: collapsible, streaming support, markdown rendering, copy and dismiss buttons.
 */

import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ChevronDownIcon,
  LanguageIcon,
  ClipboardDocumentIcon,
  ClipboardDocumentCheckIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

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
    <div data-name="translation-block" className="mt-3 border border-teal-200 dark:border-teal-800 rounded-lg overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 text-xs font-medium hover:bg-teal-100 dark:hover:bg-teal-900/50 transition-colors"
      >
        <span className={`w-4 h-4 transition-transform duration-200 ${isExpanded ? 'rotate-0' : '-rotate-90'}`}>
          <ChevronDownIcon className="w-4 h-4" />
        </span>
        <LanguageIcon className={`w-4 h-4 ${isTranslating ? 'animate-pulse' : ''}`} />
        <span>{headerText}</span>
        <span className="ml-auto flex items-center gap-1">
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
        <div className="px-3 py-2 bg-teal-50/50 dark:bg-teal-900/20 text-sm text-gray-700 dark:text-gray-300 max-h-96 overflow-y-auto prose prose-sm dark:prose-invert max-w-none">
          {translatedText ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {translatedText}
            </ReactMarkdown>
          ) : isTranslating ? (
            <span className="text-xs text-teal-500 dark:text-teal-400 animate-pulse">Translating...</span>
          ) : null}
        </div>
      )}
    </div>
  );
};
