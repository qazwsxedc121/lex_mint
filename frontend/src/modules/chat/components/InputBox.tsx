/**
 * InputBox component - message input field with send button and toolbar.
 */

import React, { useState, type KeyboardEvent } from 'react';
import { ChevronDownIcon, LightBulbIcon } from '@heroicons/react/24/outline';

// Reasoning effort options for supported models
const REASONING_EFFORT_OPTIONS = [
  { value: '', label: 'Off', description: 'No extended reasoning' },
  { value: 'low', label: 'Low', description: 'Quick reasoning' },
  { value: 'medium', label: 'Medium', description: 'Balanced reasoning' },
  { value: 'high', label: 'High', description: 'Deep reasoning' },
];

interface InputBoxProps {
  onSend: (message: string, options?: { reasoningEffort?: string }) => void;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
  // Toolbar props
  assistantSelector?: React.ReactNode;
  supportsReasoning?: boolean;
}

export const InputBox: React.FC<InputBoxProps> = ({
  onSend,
  onStop,
  disabled = false,
  isStreaming = false,
  assistantSelector,
  supportsReasoning = false,
}) => {
  const [input, setInput] = useState('');
  const [reasoningEffort, setReasoningEffort] = useState('');
  const [showReasoningMenu, setShowReasoningMenu] = useState(false);

  const handleSend = () => {
    const message = input.trim();
    if (message) {
      onSend(message, reasoningEffort ? { reasoningEffort } : undefined);
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

  const currentOption = REASONING_EFFORT_OPTIONS.find(o => o.value === reasoningEffort) || REASONING_EFFORT_OPTIONS[0];

  return (
    <div className="border-t border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-200 dark:border-gray-700">
        {/* Assistant selector */}
        {assistantSelector}

        {/* Reasoning effort selector (for supported models) */}
        {supportsReasoning && (
          <div className="relative">
            <button
              onClick={() => setShowReasoningMenu(!showReasoningMenu)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 text-sm rounded-md border transition-colors ${
                reasoningEffort
                  ? 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                  : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600'
              }`}
              title="Reasoning effort for extended thinking"
            >
              <LightBulbIcon className="h-4 w-4" />
              <span className="font-medium">{currentOption.label}</span>
              <ChevronDownIcon className={`h-3 w-3 transition-transform ${showReasoningMenu ? 'rotate-180' : ''}`} />
            </button>

            {showReasoningMenu && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowReasoningMenu(false)} />
                <div className="absolute left-0 bottom-full mb-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg z-20 border border-gray-200 dark:border-gray-700">
                  <div className="py-1">
                    {REASONING_EFFORT_OPTIONS.map((option) => (
                      <button
                        key={option.value}
                        onClick={() => {
                          setReasoningEffort(option.value);
                          setShowReasoningMenu(false);
                        }}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 ${
                          reasoningEffort === option.value
                            ? 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
                            : 'text-gray-700 dark:text-gray-300'
                        }`}
                      >
                        <div className="font-medium">{option.label}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">{option.description}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="p-4">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message... (Enter to send, Shift+Enter for new line)"
            disabled={disabled || isStreaming}
            className="flex-1 resize-none rounded-lg border border-gray-300 dark:border-gray-600 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white disabled:opacity-50"
            rows={3}
          />
          {isStreaming ? (
            <button
              onClick={onStop}
              className="px-6 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={disabled || !input.trim()}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
