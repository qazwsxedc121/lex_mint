/**
 * ChatView - Main chat view with messages and input
 *
 * Displays messages and provides input for a specific session
 */

import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { MessageList } from './components/MessageList';
import { InputBox } from './components/InputBox';
import { AssistantSelector } from './components/AssistantSelector';
import { useChat } from './hooks/useChat';
import { useChatContext } from './index';
import { getAssistant, getReasoningSupportedPatterns } from '../../services/api';

export const ChatView: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { sessionTitle, onAssistantRefresh } = useChatContext();
  const [supportsReasoning, setSupportsReasoning] = useState(false);
  const [reasoningPatterns, setReasoningPatterns] = useState<string[]>([]);
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
    stopGeneration,
    updateAssistantId,
  } = useChat(sessionId || null);

  // Load reasoning supported patterns from config
  useEffect(() => {
    const loadPatterns = async () => {
      try {
        const patterns = await getReasoningSupportedPatterns();
        setReasoningPatterns(patterns);
      } catch {
        setReasoningPatterns([]);
      }
    };
    loadPatterns();
  }, []);

  // Check if current model supports reasoning
  useEffect(() => {
    const checkReasoningSupport = async () => {
      if (!currentAssistantId || currentAssistantId.startsWith('__legacy_model_') || reasoningPatterns.length === 0) {
        setSupportsReasoning(false);
        return;
      }
      try {
        const assistant = await getAssistant(currentAssistantId);
        const modelId = assistant.model_id?.split(':')[1] || '';
        setSupportsReasoning(
          reasoningPatterns.some(p => modelId.toLowerCase().includes(p.toLowerCase()))
        );
      } catch {
        setSupportsReasoning(false);
      }
    };
    checkReasoningSupport();
  }, [currentAssistantId, reasoningPatterns]);

  const handleAssistantChange = async (assistantId: string) => {
    updateAssistantId(assistantId);
    onAssistantRefresh();
  };

  const handleSendMessage = (message: string, options?: { reasoningEffort?: string }) => {
    sendMessage(message, options);
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
        disabled={loading}
        isStreaming={isStreaming}
        supportsReasoning={supportsReasoning}
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
