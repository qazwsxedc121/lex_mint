/**
 * ChatView - Main chat view with messages and input
 *
 * Displays messages and provides input for a specific session
 */

import React, { useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { MessageList } from './components/MessageList';
import { InputBox } from './components/InputBox';
import { AssistantSelector } from './components/AssistantSelector';
import { useChat } from './hooks/useChat';
import { useModelCapabilities } from './hooks/useModelCapabilities';
import { useChatContext } from './index';
import type { UploadedFile } from '../../types/message';

export const ChatView: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { sessionTitle, onAssistantRefresh } = useChatContext();
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
  } = useChat(sessionId || null);

  // Check model capabilities (vision, reasoning)
  const { supportsVision, supportsReasoning } = useModelCapabilities(currentAssistantId);

  // Auto-refresh title after streaming completes
  useEffect(() => {
    // Detect when streaming transitions from true to false
    if (wasStreamingRef.current && !isStreaming) {
      // Streaming just completed, schedule a refresh
      const timer = setTimeout(() => {
        onAssistantRefresh();
      }, 1000);

      return () => clearTimeout(timer);
    }

    // Update ref for next comparison
    wasStreamingRef.current = isStreaming;
  }, [isStreaming, onAssistantRefresh]);

  const handleAssistantChange = async (assistantId: string) => {
    updateAssistantId(assistantId);
    onAssistantRefresh();
  };

  const handleSendMessage = (message: string, options?: { reasoningEffort?: string; attachments?: UploadedFile[] }) => {
    sendMessage(message, options);
  };

  const handleInsertSeparator = () => {
    insertSeparator();
  };

  const handleClearAllMessages = () => {
    clearAllMessages();
  };

  if (!sessionId) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500 dark:text-gray-400">
        <div className="text-center">
          <p className="text-lg mb-4">Welcome to LangGraph AI Agent</p>
          <p className="text-sm">Select a conversation or create a new one to start</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-300 dark:border-gray-700 p-4 bg-white dark:bg-gray-800">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
          {sessionTitle || 'Chat'}
        </h1>
      </div>

      {/* Messages */}
      <MessageList
        messages={messages}
        loading={loading}
        isStreaming={isStreaming}
        sessionId={sessionId}
        onEditMessage={editMessage}
        onRegenerateMessage={regenerateMessage}
        onDeleteMessage={deleteMessage}
      />

      {/* Error display */}
      {error && (
        <div className="px-4 py-2 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200 text-sm">
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
        sessionId={sessionId}
        currentAssistantId={currentAssistantId || undefined}
        assistantSelector={
          <AssistantSelector
            sessionId={sessionId}
            currentAssistantId={currentAssistantId || undefined}
            onAssistantChange={handleAssistantChange}
          />
        }
      />
    </div>
  );
};
