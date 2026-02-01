/**
 * MessageBubble component - displays a single message.
 */

import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PencilSquareIcon, ArrowPathIcon, ClipboardDocumentIcon, ClipboardDocumentCheckIcon, TrashIcon, ChevronDownIcon, ChevronRightIcon, LightBulbIcon, DocumentTextIcon, PhotoIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import type { Message } from '../../../types/message';
import { CodeBlock } from './CodeBlock';
import { useChatServices } from '../services/ChatServiceProvider';

interface MessageBubbleProps {
  message: Message;
  messageId: string;
  messageIndex: number;  // Still needed for file attachment URLs (backward compatibility)
  isStreaming: boolean;
  sessionId?: string;
  onEdit?: (messageId: string, content: string) => void;
  onRegenerate?: (messageId: string) => void;
  onDelete?: (messageId: string) => void;
  customActions?: (message: Message, messageId: string) => React.ReactNode;
}

/**
 * Parse content to extract thinking blocks and regular content.
 * Thinking content is wrapped in <think>...</think> tags.
 * Also handles streaming case where </think> hasn't arrived yet.
 */
function parseThinkingContent(content: string, isStreaming: boolean): { thinking: string; mainContent: string; isThinkingInProgress: boolean } {
  // Check for complete thinking blocks first
  const completeThinkRegex = /<think>([\s\S]*?)<\/think>/g;
  let thinking = '';
  let mainContent = content;
  let isThinkingInProgress = false;

  // Extract all complete thinking blocks
  let match;
  while ((match = completeThinkRegex.exec(content)) !== null) {
    thinking += match[1];
  }

  // Remove complete thinking tags from main content
  mainContent = content.replace(completeThinkRegex, '');

  // Handle streaming case: <think> started but </think> not yet received
  if (isStreaming && mainContent.includes('<think>') && !mainContent.includes('</think>')) {
    const thinkStart = mainContent.indexOf('<think>');
    // Everything after <think> is thinking content in progress
    thinking += mainContent.slice(thinkStart + 7); // 7 = length of '<think>'
    mainContent = mainContent.slice(0, thinkStart);
    isThinkingInProgress = true;
  }

  return { thinking: thinking.trim(), mainContent: mainContent.trim(), isThinkingInProgress };
}

/**
 * Format cost value for display.
 * Shows enough precision to be meaningful.
 */
function formatCost(cost: number): string {
  if (cost === 0) return '$0';
  if (cost < 0.000001) return `<$0.000001`;
  if (cost < 0.01) return `$${cost.toFixed(6)}`;
  if (cost < 1) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  messageId,
  messageIndex,
  isStreaming,
  sessionId,
  onEdit,
  onRegenerate,
  onDelete,
  customActions,
}) => {
  const { api } = useChatServices();
  const isUser = message.role === 'user';
  const isSeparator = message.role === 'separator';
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const [isCopied, setIsCopied] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showThinking, setShowThinking] = useState(false);

  // Parse thinking content from message
  const { thinking, mainContent, isThinkingInProgress } = useMemo(
    () => parseThinkingContent(message.content, isStreaming),
    [message.content, isStreaming]
  );

  const canEdit = isUser && !isStreaming && onEdit;
  const canRegenerate = !isStreaming && onRegenerate && message.content.trim() !== '';
  const canDelete = !isStreaming && onDelete;

  const handleDownloadAttachment = async (filename: string) => {
    if (!sessionId) return;

    try {
      const blob = await api.downloadFile(sessionId, messageIndex, filename);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(`Download failed: ${err.message}`);
    }
  };

  const handleSaveEdit = () => {
    if (editContent.trim() && onEdit) {
      onEdit(messageId, editContent.trim());
      setIsEditing(false);
    }
  };

  const handleCancelEdit = () => {
    setEditContent(message.content);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSaveEdit();
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      handleCancelEdit();
    }
  };

  const handleCopy = async () => {
    try {
      // Copy mainContent (without thinking tags) for assistant messages
      const textToCopy = isUser ? message.content : mainContent;
      await navigator.clipboard.writeText(textToCopy);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleDeleteClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (onDelete) {
      onDelete(messageId);
    }
    setShowDeleteConfirm(false);
  };

  const handleDeleteCancel = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setShowDeleteConfirm(false);
  };

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      e.preventDefault();
      e.stopPropagation();
      setShowDeleteConfirm(false);
    }
  };

  const handleDeleteSeparator = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (onDelete) {
      onDelete(messageId);
    }
  };

  // Separator rendering (centered display)
  if (isSeparator) {
    return (
      <div data-name="message-bubble-separator" className="flex flex-col items-center mb-4 group">
        <div data-name="message-bubble-separator-content" className="w-full max-w-[80%] relative">
          {/* Separator line */}
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

          {/* Delete button (on hover) */}
          {canDelete && (
            <div className="absolute -right-10 top-1/2 -translate-y-1/2">
              <button
                type="button"
                onClick={handleDeleteSeparator}
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

  return (
    <div data-name={`message-bubble-${isUser ? 'user' : 'assistant'}`} className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} mb-4`}>
      <div data-name="message-bubble-content-wrapper" className="max-w-[80%]">
        <div
          data-name="message-bubble-content"
          className={`rounded-lg px-4 py-3 ${
            isUser
              ? 'bg-blue-500 text-white'
              : 'bg-gray-200 text-gray-900 dark:bg-gray-700 dark:text-gray-100'
          }`}
        >
          {isEditing ? (
            <div className="space-y-2">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full min-h-[100px] px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={handleCancelEdit}
                  className="px-3 py-1 text-sm bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-400 dark:hover:bg-gray-500"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveEdit}
                  disabled={!editContent.trim()}
                  className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Save & Regenerate
                </button>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Tip: Ctrl+Enter to save, Esc to cancel
              </p>
            </div>
          ) : (
            <div className="text-sm prose prose-sm max-w-none dark:prose-invert">
              {/* Attachments display (for user messages) */}
              {isUser && message.attachments && message.attachments.length > 0 && (
                <div className="mb-3 space-y-2">
                  {message.attachments.map((att, idx) => {
                    const isImage = att.mime_type.startsWith('image/');

                    return isImage ? (
                      // Image attachment: show thumbnail
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
                      // Text file: show file name with icon
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
              {isUser ? (
                <p className="whitespace-pre-wrap m-0">{message.content}</p>
              ) : (
                <>
                  {/* Thinking block (collapsible, auto-expand during streaming) */}
                  {thinking && (
                    <div className="mb-3 border border-amber-200 dark:border-amber-800 rounded-lg overflow-hidden">
                      <button
                        onClick={() => setShowThinking(!showThinking)}
                        className="w-full flex items-center gap-2 px-3 py-2 bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-xs font-medium hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors"
                      >
                        {(showThinking || isThinkingInProgress) ? (
                          <ChevronDownIcon className="w-4 h-4" />
                        ) : (
                          <ChevronRightIcon className="w-4 h-4" />
                        )}
                        <LightBulbIcon className={`w-4 h-4 ${isThinkingInProgress ? 'animate-pulse' : ''}`} />
                        <span>{isThinkingInProgress ? 'Thinking...' : 'Thinking Process'}</span>
                        <span className="ml-auto text-amber-500 dark:text-amber-400">
                          {thinking.length} chars
                        </span>
                      </button>
                      {(showThinking || isThinkingInProgress) && (
                        <div className="px-3 py-2 bg-amber-50/50 dark:bg-amber-900/20 text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap max-h-64 overflow-y-auto">
                          {thinking}
                        </div>
                      )}
                    </div>
                  )}
                  {/* Main content */}
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({ className, children, ...props }: any) {
                        const match = /language-(\w+)/.exec(className || '');
                        const language = match ? match[1] : '';
                        const value = String(children).replace(/\n$/, '');
                        const isInline = !className;

                        return !isInline && language ? (
                          <CodeBlock language={language} value={value} />
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
                    {mainContent || '*Generating...*'}
                  </ReactMarkdown>
                </>
              )}
            </div>
          )}
        </div>

        {/* Token usage info for assistant messages */}
        {!isUser && !isEditing && message.usage && !isStreaming && (
          <div data-name="message-bubble-usage-info" className="flex items-center gap-2 mt-1 px-1 text-xs text-gray-400 dark:text-gray-500">
            <span>{message.usage.prompt_tokens} in</span>
            <span className="text-gray-300 dark:text-gray-600">|</span>
            <span>{message.usage.completion_tokens} out</span>
            {message.cost && message.cost.total_cost > 0 && (
              <>
                <span className="text-gray-300 dark:text-gray-600">|</span>
                <span>{formatCost(message.cost.total_cost)}</span>
              </>
            )}
          </div>
        )}

        {/* Action buttons */}
        {!isEditing && (
          <div data-name="message-bubble-actions" className="flex gap-1 mt-1">
            <button
              onClick={handleCopy}
              className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 transition-colors"
              title={isCopied ? 'Copied' : 'Copy'}
            >
              {isCopied ? (
                <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-600 dark:text-green-400" />
              ) : (
                <ClipboardDocumentIcon className="w-4 h-4" />
              )}
              <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                {isCopied ? 'Copied' : 'Copy'}
              </span>
            </button>

            {canEdit && (
              <button
                onClick={() => setIsEditing(true)}
                className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 transition-colors"
                title="Edit message"
              >
                <PencilSquareIcon className="w-4 h-4" />
                <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  Edit
                </span>
              </button>
            )}

            {canRegenerate && (
              <button
                onClick={() => onRegenerate?.(messageId)}
                className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 transition-colors"
                title="Regenerate"
              >
                <ArrowPathIcon className="w-4 h-4" />
                <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  Regenerate
                </span>
              </button>
            )}

            {/* Custom actions slot */}
            {customActions?.(message, messageId)}

            {canDelete && (
              <button
                type="button"
                onClick={handleDeleteClick}
                className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-red-100 dark:hover:bg-red-900 hover:text-red-600 dark:hover:text-red-400 border border-gray-300 dark:border-gray-600 transition-colors"
                title="Delete"
              >
                <TrashIcon className="w-4 h-4" />
                <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  Delete
                </span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div
          data-name="message-bubble-delete-confirm-backdrop"
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
          onClick={handleBackdropClick}
        >
          <div data-name="message-bubble-delete-confirm-modal" className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-sm mx-4 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
              Delete Message
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Are you sure you want to delete this message? This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={handleDeleteCancel}
                className="px-4 py-2 text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                className="px-4 py-2 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
