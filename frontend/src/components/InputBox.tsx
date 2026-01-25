/**
 * InputBox component - message input field with send button.
 */

import React, { useState, type KeyboardEvent } from 'react';

interface InputBoxProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
}

export const InputBox: React.FC<InputBoxProps> = ({
  onSend,
  onStop,
  disabled = false,
  isStreaming = false,
}) => {
  const [input, setInput] = useState('');

  const handleSend = () => {
    const message = input.trim();
    if (message) {
      onSend(message);
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter, new line on Shift+Enter
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming) {
        handleSend();
      }
    }
  };

  return (
    <div className="border-t border-gray-300 dark:border-gray-600 p-4 bg-white dark:bg-gray-800">
      <div className="flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息... (Enter发送, Shift+Enter换行)"
          disabled={disabled || isStreaming}
          className="flex-1 resize-none rounded-lg border border-gray-300 dark:border-gray-600 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white disabled:opacity-50"
          rows={3}
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="px-6 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
          >
            停止
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            发送
          </button>
        )}
      </div>
    </div>
  );
};
