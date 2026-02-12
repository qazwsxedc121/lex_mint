/**
 * ErrorMessage Component
 *
 * Displays an error message with optional retry action.
 */

import React from 'react';
import { XCircleIcon } from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';

interface ErrorMessageProps {
  /** Error message to display */
  message: string;
  /** Optional retry callback */
  onRetry?: () => void;
  /** Retry button label */
  retryLabel?: string;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  message,
  onRetry,
  retryLabel
}) => {
  const { t } = useTranslation('common');
  const resolvedRetryLabel = retryLabel ?? t('retry');
  return (
    <div
      data-name="error-message"
      className="rounded-md bg-red-50 dark:bg-red-900/20 p-4 border border-red-200 dark:border-red-800"
    >
      <div className="flex">
        <div className="flex-shrink-0">
          <XCircleIcon className="h-5 w-5 text-red-400 dark:text-red-500" />
        </div>
        <div className="ml-3 flex-1">
          <p className="text-sm text-red-800 dark:text-red-200">{message}</p>
        </div>
        {onRetry && (
          <div className="ml-3">
            <button
              onClick={onRetry}
              className="text-sm font-medium text-red-800 dark:text-red-200 hover:text-red-600 dark:hover:text-red-100 underline"
            >
              {resolvedRetryLabel}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
