/**
 * SuccessMessage Component
 *
 * Displays a success message that auto-dismisses after a delay.
 */

import React, { useEffect } from 'react';
import { CheckCircleIcon } from '@heroicons/react/24/outline';

interface SuccessMessageProps {
  /** Success message to display */
  message: string;
  /** Auto-dismiss duration in ms (0 to disable) */
  duration?: number;
  /** Callback when message is dismissed */
  onDismiss?: () => void;
}

export const SuccessMessage: React.FC<SuccessMessageProps> = ({
  message,
  duration = 3000,
  onDismiss
}) => {
  useEffect(() => {
    if (duration > 0 && onDismiss) {
      const timer = setTimeout(onDismiss, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, onDismiss]);

  return (
    <div
      data-name="success-message"
      className="rounded-md bg-green-50 dark:bg-green-900/20 p-4 border border-green-200 dark:border-green-800"
    >
      <div className="flex">
        <div className="flex-shrink-0">
          <CheckCircleIcon className="h-5 w-5 text-green-400 dark:text-green-500" />
        </div>
        <div className="ml-3 flex-1">
          <p className="text-sm text-green-800 dark:text-green-200">{message}</p>
        </div>
        {onDismiss && (
          <div className="ml-3">
            <button
              onClick={onDismiss}
              className="text-sm font-medium text-green-800 dark:text-green-200 hover:text-green-600 dark:hover:text-green-100"
            >
              ✕
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
