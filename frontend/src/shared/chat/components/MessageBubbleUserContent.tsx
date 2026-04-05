import { ArrowDownTrayIcon, ChevronDownIcon, ChevronRightIcon, DocumentTextIcon, PhotoIcon } from '@heroicons/react/24/outline';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import type { Message } from '../../../types/message';
import type { FileReferencePreviewConfig, FileReferencePreviewResult } from '../config/fileReferencePreview';
import { CodeBlock } from './CodeBlock';
import { MermaidBlock } from './MermaidBlock';
import { SvgBlock } from './SvgBlock';

interface UserBlockItem {
  id: string;
  kind: 'context' | 'block';
  title: string;
  content: string;
  language: string;
  isCodeFence: boolean;
  isAttachmentNote: boolean;
  attachmentLabel?: string;
}

interface MessageBubbleUserContentProps {
  displayUserMessage: string;
  expandedUserBlocks: Record<string, boolean>;
  fileReferencePreviewConfig: FileReferencePreviewConfig;
  handleDownloadAttachment: (filename: string) => void;
  message: Message;
  messageIndex: number;
  onToggleUserBlock: (blockId: string) => void;
  prepareMarkdownForRender: (value: string) => string;
  sessionId?: string;
  userBlocks: UserBlockItem[];
  buildFileReferencePreview: (content: string, config?: FileReferencePreviewConfig) => FileReferencePreviewResult;
}

export function MessageBubbleUserContent({
  displayUserMessage,
  expandedUserBlocks,
  fileReferencePreviewConfig,
  handleDownloadAttachment,
  message,
  messageIndex,
  onToggleUserBlock,
  prepareMarkdownForRender,
  sessionId,
  userBlocks,
  buildFileReferencePreview,
}: MessageBubbleUserContentProps) {
  return (
    <>
      {message.attachments && message.attachments.length > 0 && (
        <div className="mb-3 space-y-2">
          {message.attachments.map((att, idx) => {
            const isImage = att.mime_type.startsWith('image/');

            return isImage ? (
              <div key={idx} className="max-w-xs">
                <img
                  src={`/api/chat/attachment/${sessionId}/${messageIndex}/${encodeURIComponent(att.filename)}`}
                  alt={att.filename}
                  className="w-full rounded border border-blue-400 dark:border-blue-600 cursor-pointer hover:opacity-90"
                  onClick={() => handleDownloadAttachment(att.filename)}
                  title="Click to download"
                  loading="lazy"
                />
                <div className="flex items-center gap-1 mt-1 text-xs opacity-80">
                  <PhotoIcon className="h-3 w-3" />
                  <span className="truncate">{att.filename}</span>
                  <span>({(att.size / 1024).toFixed(1)} KB)</span>
                </div>
              </div>
            ) : (
              <div
                key={idx}
                className="flex items-center gap-2 px-3 py-2 bg-blue-600 dark:bg-blue-400/20 rounded border border-blue-400 dark:border-blue-600"
              >
                <DocumentTextIcon className="h-4 w-4 flex-shrink-0" />
                <span className="flex-1 text-sm truncate">{att.filename}</span>
                <span className="text-xs opacity-80">
                  ({(att.size / 1024).toFixed(1)} KB)
                </span>
                <button
                  onClick={() => handleDownloadAttachment(att.filename)}
                  className="flex-shrink-0 hover:opacity-80"
                  title="Download"
                >
                  <ArrowDownTrayIcon className="h-4 w-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {userBlocks.length > 0 && (
        <div data-name="user-message-blocks" className="mb-3 rounded-md border border-blue-300/40 bg-blue-600/30 overflow-hidden">
          <div className="flex items-center justify-between px-2.5 py-1 text-[11px] uppercase tracking-wide text-blue-100/80">
            <span>Blocks</span>
            <span>{userBlocks.length}</span>
          </div>
          <div className="divide-y divide-blue-400/30">
            {userBlocks.map((block) => {
              const isExpanded = !!expandedUserBlocks[block.id];
              const isFileReferenceBlock = block.title.toLowerCase().startsWith('file reference:');
              const filePreview = isFileReferenceBlock
                ? buildFileReferencePreview(block.content, fileReferencePreviewConfig)
                : null;
              const previewHiddenParts: string[] = [];
              if (filePreview?.hiddenLines) {
                previewHiddenParts.push(`${filePreview.hiddenLines} lines`);
              }
              if (filePreview?.hiddenChars) {
                previewHiddenParts.push(`${filePreview.hiddenChars} chars`);
              }
              const previewHiddenLabel = previewHiddenParts.join(', ');
              const blockDisplayContent = filePreview?.truncated
                ? `${filePreview.text}\n...\n[Preview only: ${previewHiddenLabel} hidden]`
                : block.content;
              const metaLabel = block.isAttachmentNote
                ? 'Attachment'
                : filePreview?.truncated
                  ? `preview ${filePreview.shownLines}/${filePreview.totalLines} lines, ${filePreview.shownChars}/${filePreview.totalChars} chars`
                  : `${block.content.length} chars`;

              return (
                <div key={block.id}>
                  <button
                    type="button"
                    onClick={() => onToggleUserBlock(block.id)}
                    className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-xs text-blue-50 hover:bg-blue-600/40 transition-colors"
                    title={isExpanded ? 'Collapse block' : 'Expand block'}
                  >
                    {isExpanded ? (
                      <ChevronDownIcon className="w-4 h-4 text-blue-100" />
                    ) : (
                      <ChevronRightIcon className="w-4 h-4 text-blue-100" />
                    )}
                    <span className="text-[10px] uppercase tracking-wide text-blue-100/70">
                      {block.kind}
                    </span>
                    <span className="flex-1 truncate text-blue-50">{block.title || 'Block'}</span>
                    <span className="text-[11px] text-blue-100/70">{metaLabel}</span>
                  </button>
                  {isExpanded && (
                    <div className="px-2.5 py-2 bg-blue-600/20 text-blue-50">
                      {block.isAttachmentNote ? (
                        <div className="text-xs text-blue-100/80">
                          {block.attachmentLabel || 'Attachment'}
                        </div>
                      ) : block.isCodeFence ? (
                        <CodeBlock language={block.language} value={blockDisplayContent} />
                      ) : (
                        <div className="prose prose-sm max-w-none prose-invert">
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
                            {prepareMarkdownForRender(blockDisplayContent || '_Empty block_')}
                          </ReactMarkdown>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {userBlocks.length > 0 && displayUserMessage && (
        <div className="mb-2">
          <div className="h-px bg-blue-300/40" />
        </div>
      )}
      {displayUserMessage.includes('```') ? (
        <div className="prose prose-sm max-w-none prose-invert [&_pre]:max-w-full [&_pre]:overflow-x-auto">
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
            {prepareMarkdownForRender(displayUserMessage)}
          </ReactMarkdown>
        </div>
      ) : (
        <p className="whitespace-pre-wrap m-0">{displayUserMessage}</p>
      )}
    </>
  );
}
