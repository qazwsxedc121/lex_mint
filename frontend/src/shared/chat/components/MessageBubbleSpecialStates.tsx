import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { ChevronDownIcon, ChevronRightIcon, TrashIcon } from '@heroicons/react/24/outline';
import { CodeBlock } from './CodeBlock';
import { MermaidBlock } from './MermaidBlock';
import { SvgBlock } from './SvgBlock';

interface SeparatorBubbleProps {
  canDelete: boolean;
  onDelete: React.MouseEventHandler<HTMLButtonElement>;
}

export function SeparatorBubble({ canDelete, onDelete }: SeparatorBubbleProps) {
  return (
    <div data-name="message-bubble-separator" className="flex flex-col items-center mb-4 group">
      <div data-name="message-bubble-separator-content" className="w-full max-w-[80%] relative">
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-gradient-to-r from-transparent via-amber-400 dark:via-amber-600 to-transparent" />
          <div className="flex items-center gap-2 px-4 py-2 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 rounded-lg text-amber-700 dark:text-amber-300 text-sm font-medium">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
            <span>Context Cleared</span>
          </div>
          <div className="flex-1 h-px bg-gradient-to-r from-transparent via-amber-400 dark:via-amber-600 to-transparent" />
        </div>

        {canDelete && (
          <div className="absolute -right-10 top-1/2 -translate-y-1/2">
            <button
              type="button"
              onClick={onDelete}
              className="p-1.5 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-red-100 dark:hover:bg-red-900 hover:text-red-600 dark:hover:text-red-400 border border-gray-300 dark:border-gray-600 opacity-0 group-hover:opacity-100 transition-all"
              title="Delete separator"
            >
              <TrashIcon className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

interface SummaryBubbleProps {
  canDelete: boolean;
  content: string;
  isStreaming: boolean;
  isExpanded: boolean;
  onDelete: React.MouseEventHandler<HTMLButtonElement>;
  onToggleExpanded: () => void;
  prepareMarkdownForRender: (value: string) => string;
}

export function SummaryBubble({
  canDelete,
  content,
  isStreaming,
  isExpanded,
  onDelete,
  onToggleExpanded,
  prepareMarkdownForRender,
}: SummaryBubbleProps) {
  return (
    <div data-name="message-bubble-summary" className="flex flex-col items-center mb-4 group">
      <div data-name="message-bubble-summary-content" className="w-full max-w-[80%] relative">
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-gradient-to-r from-transparent via-violet-400 dark:via-violet-600 to-transparent" />
          <button
            onClick={onToggleExpanded}
            className="flex items-center gap-2 px-4 py-2 bg-violet-50 dark:bg-violet-900/30 border border-violet-200 dark:border-violet-800 rounded-lg text-violet-700 dark:text-violet-300 text-sm font-medium hover:bg-violet-100 dark:hover:bg-violet-900/50 transition-colors"
          >
            {isExpanded ? (
              <ChevronDownIcon className="w-4 h-4" />
            ) : (
              <ChevronRightIcon className="w-4 h-4" />
            )}
            <svg className={`w-4 h-4 ${isStreaming ? 'animate-pulse' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span>{isStreaming ? 'Compressing Context...' : 'Context Compressed'}</span>
          </button>
          <div className="flex-1 h-px bg-gradient-to-r from-transparent via-violet-400 dark:via-violet-600 to-transparent" />
        </div>

        {isExpanded && content && (
          <div className="mt-2 px-4 py-3 bg-violet-50/50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 rounded-lg text-sm text-gray-700 dark:text-gray-300 max-h-96 overflow-y-auto">
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
                  code({ className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || '');
                    const language = match ? match[1] : '';
                    const value = String(children).replace(/\n$/, '');
                    const isInline = !className;

                    return !isInline && language ? (
                      language === 'mermaid'
                        ? <MermaidBlock value={value} />
                        : language === 'svg'
                          ? <SvgBlock value={value} />
                          : <CodeBlock language={language} value={value} />
                    ) : (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {prepareMarkdownForRender(content)}
              </ReactMarkdown>
            </div>
          </div>
        )}

        {canDelete && (
          <div className="absolute -right-10 top-1/2 -translate-y-1/2">
            <button
              type="button"
              onClick={onDelete}
              className="p-1.5 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-red-100 dark:hover:bg-red-900 hover:text-red-600 dark:hover:text-red-400 border border-gray-300 dark:border-gray-600 opacity-0 group-hover:opacity-100 transition-all"
              title="Delete summary"
            >
              <TrashIcon className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
