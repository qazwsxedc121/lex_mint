/**
 * MessageBubble component - displays a single message.
 */

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PencilSquareIcon, ArrowPathIcon, ClipboardDocumentIcon, ClipboardDocumentCheckIcon } from '@heroicons/react/24/outline';
import type { Message } from '../types/message';
import { CodeBlock } from './CodeBlock';

interface MessageBubbleProps {
  message: Message;
  messageIndex: number;
  isStreaming: boolean;
  onEdit?: (index: number, content: string) => void;
  onRegenerate?: (index: number) => void;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  messageIndex,
  isStreaming,
  onEdit,
  onRegenerate,
}) => {
  const isUser = message.role === 'user';
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const [isCopied, setIsCopied] = useState(false);

  // 判断是否可以编辑/重新生成
  const canEdit = isUser && !isStreaming && onEdit;
  const canRegenerate = !isUser && !isStreaming && onRegenerate && message.content.trim() !== '';

  const handleSaveEdit = () => {
    if (editContent.trim() && onEdit) {
      onEdit(messageIndex, editContent.trim());
      setIsEditing(false);
    }
  };

  const handleCancelEdit = () => {
    setEditContent(message.content);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl/Cmd + Enter to save
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSaveEdit();
    }
    // Escape to cancel
    if (e.key === 'Escape') {
      e.preventDefault();
      handleCancelEdit();
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setIsCopied(true);
      // 2秒后恢复图标
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} mb-4`}>
      <div className="max-w-[80%]">
        <div
          className={`rounded-lg px-4 py-3 ${
            isUser
              ? 'bg-blue-500 text-white'
              : 'bg-gray-200 text-gray-900 dark:bg-gray-700 dark:text-gray-100'
          }`}
        >
          {isEditing ? (
            // 编辑模式
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
                  取消
                </button>
                <button
                  onClick={handleSaveEdit}
                  disabled={!editContent.trim()}
                  className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  保存并重新生成
                </button>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                提示：Ctrl+Enter 保存，Esc 取消
              </p>
            </div>
          ) : (
            // 显示模式
            <div className="text-sm prose prose-sm max-w-none dark:prose-invert">
              {isUser ? (
                <p className="whitespace-pre-wrap m-0">{message.content}</p>
              ) : (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // 自定义代码块渲染
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
                    // 自定义表格样式
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
                  {message.content || '*生成中...*'}
                </ReactMarkdown>
              )}
            </div>
          )}
        </div>

        {/* 操作按钮（显示在消息下方） */}
        {!isEditing && (
          <div className="flex gap-1 mt-1">
            {/* 复制按钮 - 所有消息都显示 */}
            <button
              onClick={handleCopy}
              className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 transition-colors"
              title={isCopied ? '已复制' : '复制'}
            >
              {isCopied ? (
                <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-600 dark:text-green-400" />
              ) : (
                <ClipboardDocumentIcon className="w-4 h-4" />
              )}
              {/* Hover 文字提示 */}
              <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                {isCopied ? '已复制' : '复制'}
              </span>
            </button>

            {/* 编辑按钮 - 仅用户消息 */}
            {canEdit && (
              <button
                onClick={() => setIsEditing(true)}
                className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 transition-colors"
                title="编辑消息"
              >
                <PencilSquareIcon className="w-4 h-4" />
                {/* Hover 文字提示 */}
                <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  编辑
                </span>
              </button>
            )}

            {/* 重新生成按钮 - 仅助手消息 */}
            {canRegenerate && (
              <button
                onClick={() => onRegenerate?.(messageIndex)}
                className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 transition-colors"
                title="重新生成"
              >
                <ArrowPathIcon className="w-4 h-4" />
                {/* Hover 文字提示 */}
                <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  重新生成
                </span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
