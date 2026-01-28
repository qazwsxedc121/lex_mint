/**
 * ChatContainer component - main container for the chat interface.
 */

import React, { useState } from 'react';
import { Cog6ToothIcon } from '@heroicons/react/24/outline';
import { MessageList } from './MessageList';
import { InputBox } from './InputBox';
import { Sidebar } from './Sidebar';
import { ModelSettings } from './ModelSettings';
import { AssistantSelector } from './AssistantSelector';
import { useChat } from '../hooks/useChat';
import { useSessions } from '../hooks/useSessions';

export const ChatContainer: React.FC = () => {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [assistantRefreshKey, setAssistantRefreshKey] = useState(0);
  const { sessions, createSession, deleteSession } = useSessions();
  const {
    messages,
    loading,
    error,
    isStreaming,
    currentAssistantId,
    sendMessage,
    editMessage,
    regenerateMessage,
    stopGeneration,
    updateAssistantId,
  } = useChat(currentSessionId);

  const handleNewSession = async () => {
    try {
      const sessionId = await createSession();
      setCurrentSessionId(sessionId);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
      // If deleted session was active, clear current session
      if (currentSessionId === sessionId) {
        setCurrentSessionId(null);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const handleSendMessage = async (message: string) => {
    await sendMessage(message);
  };

  const handleAssistantChange = async (assistantId: string) => {
    // Update the current assistant ID in the UI immediately
    updateAssistantId(assistantId);
  };

  const handleSettingsClose = () => {
    setShowSettings(false);
    // Trigger assistant list refresh when settings close
    setAssistantRefreshKey(prev => prev + 1);
  };

  return (
    <div className="flex h-screen bg-white dark:bg-gray-900">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="border-b border-gray-300 dark:border-gray-700 p-4 bg-white dark:bg-gray-800 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            {currentSessionId
              ? sessions.find(s => s.session_id === currentSessionId)?.title || '对话'
              : 'LangGraph AI Agent'}
          </h1>

          <div className="flex items-center gap-3">
            {/* Assistant selector */}
            {currentSessionId && (
              <AssistantSelector
                key={assistantRefreshKey}
                sessionId={currentSessionId}
                currentAssistantId={currentAssistantId || undefined}
                onAssistantChange={handleAssistantChange}
              />
            )}

            {/* Settings button */}
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
              title="Settings"
            >
              <Cog6ToothIcon className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Messages */}
        {currentSessionId ? (
          <>
            <MessageList
              messages={messages}
              loading={loading}
              isStreaming={isStreaming}
              onEditMessage={editMessage}
              onRegenerateMessage={regenerateMessage}
            />
            {error && (
              <div className="px-4 py-2 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200 text-sm">
                错误: {error}
              </div>
            )}
            <InputBox
              onSend={handleSendMessage}
              onStop={stopGeneration}
              disabled={loading}
              isStreaming={isStreaming}
            />
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500 dark:text-gray-400">
            <div className="text-center">
              <p className="text-lg mb-4">Welcome to LangGraph AI Agent</p>
              <p className="text-sm">Select a conversation or create a new one to start</p>
            </div>
          </div>
        )}
      </div>

      {/* Settings modal */}
      <ModelSettings
        isOpen={showSettings}
        onClose={handleSettingsClose}
      />
    </div>
  );
};
