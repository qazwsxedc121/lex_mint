/**
 * MessageList component - displays all messages in a conversation.
 */

import React, { useEffect, useRef } from 'react';
import type { Message } from '../types/message';
import { MessageBubble } from './MessageBubble';

interface MessageListProps {
  messages: Message[];
  loading?: boolean;
  isStreaming?: boolean;
  onEditMessage?: (index: number, content: string) => void;
  onRegenerateMessage?: (index: number) => void;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  loading = false,
  isStreaming = false,
  onEditMessage,
  onRegenerateMessage,
}) => {
  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-4 bg-gray-50 dark:bg-gray-900">
      {messages.length === 0 ? (
        <div className="flex items-center justify-center h-full text-gray-500 dark:text-gray-400">
          <p>开始新对话...</p>
        </div>
      ) : (
        <>
          {messages.map((message, index) => (
            <MessageBubble
              key={index}
              message={message}
              messageIndex={index}
              isStreaming={isStreaming}
              onEdit={onEditMessage}
              onRegenerate={onRegenerateMessage}
            />
          ))}
          {loading && (
            <div className="flex justify-start mb-4">
              <div className="bg-gray-200 dark:bg-gray-700 rounded-lg px-4 py-3">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
        </>
      )}
      <div ref={endOfMessagesRef} />
    </div>
  );
};
