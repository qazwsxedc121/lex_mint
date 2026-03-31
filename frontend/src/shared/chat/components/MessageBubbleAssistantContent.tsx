import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { CodeBlock } from './CodeBlock';
import { MermaidBlock } from './MermaidBlock';
import { SvgBlock } from './SvgBlock';
import { ThinkingBlock } from './ThinkingBlock';
import { ToolCallBlock } from './ToolCallBlock';
import { TranslationBlock } from './TranslationBlock';
import { CompareResponseView } from './CompareResponseView';
import type { Message } from '../../../types/message';

interface MessageBubbleAssistantContentProps {
  formatRagSnippet: (content?: string) => string;
  isStreaming: boolean;
  isThinkingInProgress: boolean;
  latestRagDiagnostics: any;
  mainContent: string;
  message: Message;
  otherSources: any[];
  prepareMarkdownForRender: (value: string) => string;
  ragSources: any[];
  sessionId?: string;
  showTranslation: boolean;
  thinking: string;
  translatedText: string;
  isTranslating: boolean;
  onDismissTranslation: () => void;
}

export function MessageBubbleAssistantContent({
  formatRagSnippet,
  isStreaming,
  isThinkingInProgress,
  latestRagDiagnostics,
  mainContent,
  message,
  otherSources,
  prepareMarkdownForRender,
  ragSources,
  sessionId,
  showTranslation,
  thinking,
  translatedText,
  isTranslating,
  onDismissTranslation,
}: MessageBubbleAssistantContentProps) {
  if (message.compareResponses && message.compareResponses.length > 0) {
    return (
      <CompareResponseView
        responses={message.compareResponses}
        isStreaming={isStreaming && !message.message_id}
      />
    );
  }

  return (
    <div className="min-w-0 max-w-full break-words [overflow-wrap:anywhere] prose prose-sm max-w-none dark:prose-invert [&_a]:break-all [&_code]:break-words [&_li]:break-words [&_p]:break-words [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_pre]:whitespace-pre-wrap">
      {latestRagDiagnostics && (
        <div data-name="message-bubble-rag-diagnostics" className="not-prose mb-3 rounded-md border border-amber-200 dark:border-amber-700 bg-amber-50/70 dark:bg-amber-900/30">
          <div className="flex items-center justify-between px-3 py-2 text-xs font-medium text-amber-800 dark:text-amber-200">
            <span>RAG Diagnostics</span>
            <span>
              {(latestRagDiagnostics.retrieval_mode || 'vector')}
              {' / '}
              {(latestRagDiagnostics.reorder_strategy || 'long_context')}
            </span>
          </div>
          <div className="px-3 pb-2 text-[11px] text-amber-800/90 dark:text-amber-200/90 space-y-1">
            <div>
              raw {latestRagDiagnostics.raw_count ?? 0}{' -> '}dedup {latestRagDiagnostics.deduped_count ?? 0}{' -> '}diversified {latestRagDiagnostics.diversified_count ?? 0}{' -> '}selected {latestRagDiagnostics.selected_count ?? 0}
            </div>
            <div>
              top_k {latestRagDiagnostics.top_k ?? '-'}
              {' | '}recall_k {latestRagDiagnostics.recall_k ?? '-'}
              {' | '}max_per_doc {latestRagDiagnostics.max_per_doc ?? '-'}
              {' | '}threshold {latestRagDiagnostics.score_threshold != null ? latestRagDiagnostics.score_threshold.toFixed(2) : '-'}
              {' | '}kb {(latestRagDiagnostics.searched_kb_count ?? 0)}/{(latestRagDiagnostics.requested_kb_count ?? latestRagDiagnostics.searched_kb_count ?? 0)}
              {' | '}best {latestRagDiagnostics.best_score != null ? latestRagDiagnostics.best_score.toFixed(3) : '-'}
            </div>
            <div>
              vector_raw {latestRagDiagnostics.vector_raw_count ?? '-'}
              {' | '}bm25_raw {latestRagDiagnostics.bm25_raw_count ?? '-'}
              {' | '}bm25_cov {latestRagDiagnostics.bm25_min_term_coverage != null ? latestRagDiagnostics.bm25_min_term_coverage.toFixed(2) : '-'}
            </div>
            <div>
              tool_search {latestRagDiagnostics.tool_search_count ?? 0}
              {' | '}tool_unique {latestRagDiagnostics.tool_search_unique_count ?? 0}
              {' | '}tool_dup {latestRagDiagnostics.tool_search_duplicate_count ?? 0}
              {' | '}tool_read {latestRagDiagnostics.tool_read_count ?? 0}
              {' | '}tool_finalize {latestRagDiagnostics.tool_finalize_reason || '-'}
            </div>
          </div>
        </div>
      )}

      {ragSources.length > 0 && (
        <div data-name="message-bubble-rag-sources" className="not-prose mb-3 rounded-md border border-emerald-200 dark:border-emerald-700 bg-emerald-50/60 dark:bg-emerald-900/30">
          <div className="flex items-center justify-between px-3 py-2 text-xs font-medium text-emerald-800 dark:text-emerald-200">
            <span>Knowledge Base</span>
            <span>{ragSources.length}</span>
          </div>
          <div className="px-3 pb-2 space-y-2">
            {ragSources.map((source, index) => (
              <div key={`rag-${source.kb_id || 'kb'}-${source.doc_id || index}`} className="text-xs">
                <div className="font-medium text-emerald-900 dark:text-emerald-100">
                  {source.filename || source.title || `Chunk ${source.chunk_index ?? index + 1}`}
                </div>
                <div className="text-[11px] text-emerald-700/90 dark:text-emerald-300/90">
                  {source.kb_id && `KB: ${source.kb_id}`}
                  {source.chunk_index != null && ` • Chunk ${source.chunk_index}`}
                  {source.score != null && ` • Score ${source.score.toFixed(3)}`}
                </div>
                {source.content && (
                  <div className="text-[11px] text-emerald-800/90 dark:text-emerald-200/90 mt-1">
                    {formatRagSnippet(source.content)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {otherSources.length > 0 && (
        <div data-name="message-bubble-sources" className="not-prose mb-3 rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40">
          <div className="flex items-center justify-between px-3 py-2 text-xs font-medium text-slate-700 dark:text-slate-300">
            <span>Sources</span>
            <span>{otherSources.length}</span>
          </div>
          <div className="px-3 pb-2 space-y-2">
            {otherSources.map((source, index) => {
              const isMemorySource = source.type === 'memory';
              const memoryScope = source.scope || 'global';
              const memoryLayer = source.layer || 'preference';

              return (
                <div key={`${source.id || source.url || source.title || 'source'}-${index}`} className="text-xs">
                  {isMemorySource ? (
                    <>
                      <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
                        <span className="rounded border border-violet-200 dark:border-violet-700 bg-violet-50 dark:bg-violet-900/30 px-1.5 py-0.5 text-[11px] font-medium text-violet-700 dark:text-violet-300">
                          Memory
                        </span>
                        <span className="text-[11px] text-slate-500 dark:text-slate-400">
                          {memoryScope}/{memoryLayer}
                        </span>
                        {source.score != null && (
                          <span className="text-[11px] text-slate-500 dark:text-slate-400">
                            Score {source.score.toFixed(3)}
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 whitespace-pre-wrap break-all">
                        {source.content || source.snippet || source.title || 'Memory entry'}
                      </div>
                    </>
                  ) : source.url ? (
                    <>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-600 dark:text-blue-400 hover:underline break-all"
                      >
                        {source.title || source.url}
                      </a>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 break-all">
                        {source.url}
                      </div>
                    </>
                  ) : (
                    <div className="text-slate-700 dark:text-slate-300 break-all">
                      {source.title || 'Source'}
                    </div>
                  )}
                  {!isMemorySource && source.snippet && (
                    <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 break-words">
                      {source.snippet}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {thinking && (
        <ThinkingBlock
          thinking={thinking}
          isThinkingInProgress={isThinkingInProgress}
          thinkingDurationMs={message.thinkingDurationMs}
        />
      )}

      {message.toolCalls && message.toolCalls.length > 0 && (
        <ToolCallBlock toolCalls={message.toolCalls} sessionId={sessionId} />
      )}

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
          table({ children }) {
            return (
              <div className="overflow-x-auto my-4">
                <table className="min-w-full divide-y divide-gray-300 dark:divide-gray-600">
                  {children}
                </table>
              </div>
            );
          },
          thead({ children }) {
            return (
              <thead className="bg-gray-100 dark:bg-gray-800">
                {children}
              </thead>
            );
          },
          tbody({ children }) {
            return (
              <tbody className="bg-white dark:bg-gray-700 divide-y divide-gray-200 dark:divide-gray-600">
                {children}
              </tbody>
            );
          },
          th({ children }) {
            return (
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                {children}
              </th>
            );
          },
          td({ children }) {
            return (
              <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                {children}
              </td>
            );
          },
        }}
      >
        {prepareMarkdownForRender(mainContent || '*Generating...*')}
      </ReactMarkdown>

      {showTranslation && (
        <TranslationBlock
          translatedText={translatedText}
          isTranslating={isTranslating}
          onDismiss={onDismissTranslation}
        />
      )}
    </div>
  );
}
