/**
 * InputBox component - message input field with send button and toolbar.
 */

import React, { useState, useRef, type KeyboardEvent } from 'react';
import { ChevronDownIcon, LightBulbIcon, PaperClipIcon, XMarkIcon, DocumentTextIcon, PhotoIcon } from '@heroicons/react/24/outline';
import { useChatServices } from '../services/ChatServiceProvider';
import type { UploadedFile } from '../../../types/message';

// Reasoning effort options for supported models
const REASONING_EFFORT_OPTIONS = [
  { value: '', label: 'Off', description: 'No extended reasoning' },
  { value: 'low', label: 'Low', description: 'Quick reasoning' },
  { value: 'medium', label: 'Medium', description: 'Balanced reasoning' },
  { value: 'high', label: 'High', description: 'Deep reasoning' },
];

interface InputBoxProps {
  onSend: (message: string, options?: { reasoningEffort?: string; attachments?: UploadedFile[] }) => void;
  onStop?: () => void;
  onInsertSeparator?: () => void;
  onClearAllMessages?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
  // Toolbar props
  assistantSelector?: React.ReactNode;
  supportsReasoning?: boolean;
  supportsVision?: boolean;
  sessionId?: string;
  currentAssistantId?: string;
}

export const InputBox: React.FC<InputBoxProps> = ({
  onSend,
  onStop,
  onInsertSeparator,
  onClearAllMessages,
  disabled = false,
  isStreaming = false,
  assistantSelector,
  supportsReasoning = false,
  supportsVision = false,
  sessionId,
  currentAssistantId: _currentAssistantId,
}) => {
  const { api } = useChatServices();
  const [input, setInput] = useState('');
  const [reasoningEffort, setReasoningEffort] = useState('');
  const [showReasoningMenu, setShowReasoningMenu] = useState(false);
  const [attachments, setAttachments] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || !sessionId) return;

    setUploading(true);
    try {
      const uploaded: UploadedFile[] = [];
      for (const file of Array.from(files)) {
        // Validate size on client side (10MB limit)
        if (file.size > 10 * 1024 * 1024) {
          alert(`File ${file.name} exceeds 10MB limit`);
          continue;
        }

        // Check if file is an image
        const isImage = file.type.startsWith('image/');
        if (isImage && !supportsVision) {
          alert(`Current model does not support image input. Please use a vision-capable model like GPT-4V or Claude 3.`);
          continue;
        }

        const result = await api.uploadFile(sessionId, file);
        uploaded.push(result);
      }
      setAttachments(prev => [...prev, ...uploaded]);
    } catch (err: any) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRemoveAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  const handleSend = () => {
    const message = input.trim();
    if (message || attachments.length > 0) {
      onSend(message, {
        reasoningEffort: reasoningEffort || undefined,
        attachments: attachments.length > 0 ? attachments : undefined,
      });
      setInput('');
      setAttachments([]);
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

  const handleClearClick = () => {
    setShowClearConfirm(true);
  };

  const handleClearConfirm = () => {
    setShowClearConfirm(false);
    onClearAllMessages?.();
  };

  const handleClearCancel = () => {
    setShowClearConfirm(false);
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      setShowClearConfirm(false);
    }
  };

  const currentOption = REASONING_EFFORT_OPTIONS.find(o => o.value === reasoningEffort) || REASONING_EFFORT_OPTIONS[0];

  return (
    <div className="border-t border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-200 dark:border-gray-700">
        {/* Assistant selector */}
        {assistantSelector}

        {/* Clear context button */}
        {onInsertSeparator && (
          <button
            onClick={onInsertSeparator}
            disabled={isStreaming}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-sm rounded-md border bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-amber-50 dark:hover:bg-amber-900/30 hover:text-amber-700 dark:hover:text-amber-300 hover:border-amber-200 dark:hover:border-amber-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Clear context (insert separator)"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
            <span className="font-medium">Clear Context</span>
          </button>
        )}

        {/* Clear all messages button */}
        {onClearAllMessages && (
          <button
            onClick={handleClearClick}
            disabled={isStreaming}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-sm rounded-md border bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-red-50 dark:hover:bg-red-900/30 hover:text-red-700 dark:hover:text-red-300 hover:border-red-200 dark:hover:border-red-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Clear all messages"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            <span className="font-medium">Clear Messages</span>
          </button>
        )}

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

        {/* File upload button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading || isStreaming || !sessionId}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-sm rounded-md border bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title={supportsVision ? "Attach file or image (max 10MB)" : "Attach text file (max 10MB)"}
        >
          <PaperClipIcon className="h-4 w-4" />
          {uploading && <span className="text-xs">Uploading...</span>}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={supportsVision
            ? "text/*,.txt,.md,.json,.csv,.log,.xml,.yaml,.yml,.py,.js,.ts,.java,.cpp,.go,.rs,.html,.css,image/*,.jpg,.jpeg,.png,.gif,.webp"
            : "text/*,.txt,.md,.json,.csv,.log,.xml,.yaml,.yml,.py,.js,.ts,.java,.cpp,.go,.rs,.html,.css"
          }
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {/* Attachment preview */}
      {attachments.length > 0 && (
        <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 space-y-1">
          {attachments.map((att, idx) => {
            const isImage = att.mime_type.startsWith('image/');
            return (
              <div
                key={idx}
                className="flex items-center gap-2 px-3 py-2 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded border border-blue-200 dark:border-blue-800"
              >
                {isImage ? (
                  <PhotoIcon className="h-4 w-4 flex-shrink-0" />
                ) : (
                  <DocumentTextIcon className="h-4 w-4 flex-shrink-0" />
                )}
                <span className="flex-1 text-sm truncate">{att.filename}</span>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  ({(att.size / 1024).toFixed(1)} KB)
                </span>
                <button
                  onClick={() => handleRemoveAttachment(idx)}
                  className="flex-shrink-0 hover:text-red-600 dark:hover:text-red-400"
                  title="Remove file"
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}

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
              disabled={disabled || (!input.trim() && attachments.length === 0)}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          )}
        </div>
      </div>

      {/* Clear messages confirmation dialog */}
      {showClearConfirm && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
          onClick={handleBackdropClick}
        >
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-sm mx-4 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
              Clear All Messages
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Are you sure you want to clear all messages? This action cannot be undone and will delete the entire conversation history.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleClearCancel}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleClearConfirm}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 transition-colors"
              >
                Clear All
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
