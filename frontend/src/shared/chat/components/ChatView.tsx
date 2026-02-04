/**
 * ChatView - Main chat view with messages and input
 *
 * Version 2.0: Uses currentSessionId from service
 */

import React, { useEffect, useRef } from 'react';
import { MessageList } from './MessageList';
import { InputBox } from './InputBox';
import { AssistantSelector } from './AssistantSelector';
import { useChat } from '../hooks/useChat';
import { useModelCapabilities } from '../hooks/useModelCapabilities';
import { useChatServices } from '../services/ChatServiceProvider';
import type { UploadedFile } from '../../../types/message';
import type { Message } from '../../../types/message';

export interface ChatViewProps {
  /**
   * Whether to show the header with session title
   * Default: true (shown in chat module)
   * Set to false in project module where SessionSelector is used
   */
  showHeader?: boolean;
  /**
   * Custom action buttons to render for each message
   */
  customMessageActions?: (message: Message, messageId: string) => React.ReactNode;
}

export const ChatView: React.FC<ChatViewProps> = ({ showHeader = true, customMessageActions }) => {
  const { currentSessionId, currentSession, refreshSessions, context } = useChatServices();

  // Use onAssistantRefresh from service context if available
  const { onAssistantRefresh } = context || {};

  const wasStreamingRef = useRef(false);
  const {
    messages,
    loading,
    error,
    isStreaming,
    currentAssistantId,
    sendMessage,
    editMessage,
    regenerateMessage,
    deleteMessage,
    insertSeparator,
    clearAllMessages,
    stopGeneration,
    updateAssistantId,
  } = useChat(currentSessionId);

  // Check model capabilities (vision, reasoning)
  const { supportsVision, supportsReasoning } = useModelCapabilities(currentAssistantId);

  // Auto-refresh title after streaming completes
  useEffect(() => {
    // Detect when streaming transitions from true to false
    if (wasStreamingRef.current && !isStreaming) {
      // Streaming just completed, schedule a refresh
      const timer = setTimeout(() => {
        if (onAssistantRefresh) {
          onAssistantRefresh();
        } else {
          refreshSessions();
        }
      }, 1000);

      return () => clearTimeout(timer);
    }

    // Update ref for next comparison
    wasStreamingRef.current = isStreaming;
  }, [isStreaming, onAssistantRefresh, refreshSessions]);

  const handleAssistantChange = async (assistantId: string) => {
    updateAssistantId(assistantId);
    if (onAssistantRefresh) {
      onAssistantRefresh();
    } else {
      await refreshSessions();
    }
  };

  const handleSendMessage = (message: string, options?: { reasoningEffort?: string; attachments?: UploadedFile[]; useWebSearch?: boolean }) => {
    sendMessage(message, options);
  };

  const handleInsertSeparator = () => {
    insertSeparator();
  };

  const handleClearAllMessages = () => {
    clearAllMessages();
  };

  if (!currentSessionId) {
    return (
      <div data-name="chat-view-welcome" className="flex-1 flex items-center justify-center text-gray-500 dark:text-gray-400">
        <div className="text-center">
          <p className="text-lg mb-4">Welcome to LangGraph AI Agent</p>
          <p className="text-sm">Select a conversation or create a new one to start</p>
        </div>
      </div>
    );
  }

  return (
    <div data-name="chat-view-root" className="flex flex-col flex-1 min-h-0">
      {/* Header (optional) */}
      {showHeader && (
        <div data-name="chat-view-header" className="border-b border-gray-300 dark:border-gray-700 p-4 bg-white dark:bg-gray-800">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            {currentSession?.title || 'Chat'}
          </h1>
        </div>
      )}

      {/* Messages */}
      <MessageList
        messages={messages}
        loading={loading}
        isStreaming={isStreaming}
        sessionId={currentSessionId}
        onEditMessage={editMessage}
        onRegenerateMessage={regenerateMessage}
        onDeleteMessage={deleteMessage}
        customMessageActions={customMessageActions}
      />

      {/* Error display */}
      {error && (
        <div data-name="chat-view-error" className="px-4 py-2 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200 text-sm">
          Error: {error}
        </div>
      )}

      {/* Input with toolbar */}
      <InputBox
        onSend={handleSendMessage}
        onStop={stopGeneration}
        onInsertSeparator={handleInsertSeparator}
        onClearAllMessages={handleClearAllMessages}
        disabled={loading}
        isStreaming={isStreaming}
        supportsReasoning={supportsReasoning}
        supportsVision={supportsVision}
        sessionId={currentSessionId}
        currentAssistantId={currentAssistantId || undefined}
        assistantSelector={
          <AssistantSelector
            sessionId={currentSessionId}
            currentAssistantId={currentAssistantId || undefined}
            onAssistantChange={handleAssistantChange}
          />
        }
      />
    </div>
  );
};
