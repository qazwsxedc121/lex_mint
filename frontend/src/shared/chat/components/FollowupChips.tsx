/**
 * FollowupChips - Display follow-up question suggestions as clickable pill buttons
 */

import React from 'react';

interface FollowupChipsProps {
  questions: string[];
  onSelect: (question: string) => void;
  disabled?: boolean;
}

export const FollowupChips: React.FC<FollowupChipsProps> = ({
  questions,
  onSelect,
  disabled = false
}) => {
  if (!questions || questions.length === 0) {
    return null;
  }

  return (
    <div
      data-name="followup-chips"
      className="px-4 py-3 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700"
    >
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
        Suggested follow-ups:
      </div>
      <div className="flex flex-wrap gap-2">
        {questions.map((question, index) => (
          <button
            key={index}
            onClick={() => onSelect(question)}
            disabled={disabled}
            className={`
              px-3 py-1.5 text-sm rounded-full border
              transition-colors duration-150
              ${disabled
                ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 border-gray-200 dark:border-gray-600 cursor-not-allowed'
                : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:border-blue-300 dark:hover:border-blue-700 hover:text-blue-700 dark:hover:text-blue-300 cursor-pointer'
              }
            `}
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  );
};
