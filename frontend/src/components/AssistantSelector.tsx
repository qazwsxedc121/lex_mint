/**
 * Assistant selector component
 *
 * Displays current assistant in chat interface, supports switching
 */

import React, { useState, useEffect } from 'react';
import { ChevronDownIcon } from '@heroicons/react/24/outline';
import { listAssistants, updateSessionAssistant } from '../services/api';
import type { Assistant } from '../types/assistant';

interface AssistantSelectorProps {
  sessionId: string;
  currentAssistantId?: string;
  onAssistantChange?: (assistantId: string) => void;
}

export const AssistantSelector: React.FC<AssistantSelectorProps> = ({
  sessionId,
  currentAssistantId,
  onAssistantChange,
}) => {
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  // Load assistants list
  useEffect(() => {
    const loadAssistants = async () => {
      try {
        const data = await listAssistants();
        // Only show enabled assistants
        setAssistants(data.filter((a) => a.enabled));
      } catch (error) {
        console.error('Failed to load assistants:', error);
      } finally {
        setLoading(false);
      }
    };
    loadAssistants();
  }, []);

  // Current selected assistant
  const currentAssistant = assistants.find((a) => a.id === currentAssistantId);

  const handleSelectAssistant = async (assistant: Assistant) => {
    if (assistant.id === currentAssistantId) {
      setIsOpen(false);
      return;
    }

    try {
      await updateSessionAssistant(sessionId, assistant.id);
      onAssistantChange?.(assistant.id);
      setIsOpen(false);
    } catch (error) {
      console.error('Failed to update assistant:', error);
      alert('Failed to switch assistant');
    }
  };

  if (loading) {
    return (
      <div className="text-sm text-gray-500 dark:text-gray-400">
        Loading...
      </div>
    );
  }

  // Display for legacy sessions (starts with __legacy_model_)
  const isLegacySession = currentAssistantId?.startsWith('__legacy_model_');
  const displayName = isLegacySession
    ? 'Legacy Session'
    : currentAssistant?.name || 'Unknown Assistant';

  return (
    <div className="relative">
      {/* Current assistant display button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-md hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors border border-blue-200 dark:border-blue-800"
        title={currentAssistant?.description || 'Select assistant'}
      >
        <span className="font-medium">{displayName}</span>
        <ChevronDownIcon
          className={`h-4 w-4 transition-transform ${
            isOpen ? 'transform rotate-180' : ''
          }`}
        />
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <>
          {/* Overlay */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Menu content */}
          <div className="absolute right-0 mt-2 w-80 bg-white dark:bg-gray-800 rounded-md shadow-lg z-20 border border-gray-200 dark:border-gray-700 max-h-96 overflow-y-auto">
            <div className="py-2">
              {assistants.map((assistant) => {
                const isSelected = assistant.id === currentAssistantId;

                return (
                  <button
                    key={assistant.id}
                    onClick={() => handleSelectAssistant(assistant)}
                    className={`w-full text-left px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                      isSelected
                        ? 'bg-blue-50 dark:bg-blue-900/30 border-l-4 border-blue-500'
                        : ''
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className={`font-medium text-sm ${
                          isSelected
                            ? 'text-blue-600 dark:text-blue-300'
                            : 'text-gray-900 dark:text-gray-100'
                        }`}>
                          {assistant.name}
                        </div>
                        {assistant.description && (
                          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            {assistant.description}
                          </div>
                        )}
                        <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                          Model: {assistant.model_id}
                          {assistant.temperature !== null && assistant.temperature !== undefined && (
                            <span className="ml-2">
                              Temp: {assistant.temperature}
                            </span>
                          )}
                        </div>
                      </div>
                      {isSelected && (
                        <div className="ml-2">
                          <svg className="h-5 w-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}

              {assistants.length === 0 && (
                <div className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">
                  No assistants available
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
