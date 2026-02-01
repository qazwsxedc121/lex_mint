/**
 * ChatWelcome - Welcome screen when no session is selected
 */

import React from 'react';

export const ChatWelcome: React.FC = () => {
  return (
    <div data-name="chat-welcome-root" className="flex-1 flex items-center justify-center text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900">
      <div data-name="chat-welcome-content" className="text-center">
        <p className="text-lg mb-4">Welcome to LangGraph AI Agent</p>
        <p className="text-sm">Select a conversation or create a new one to start</p>
      </div>
    </div>
  );
};
