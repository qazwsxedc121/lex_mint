/**
 * LoadingSpinner Component
 *
 * Displays a loading state with spinner animation.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';

interface LoadingSpinnerProps {
  /** Loading message to display */
  message?: string;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  message,
  size = 'md'
}) => {
  const { t } = useTranslation('common');
  const resolvedMessage = message ?? t('loading');
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12'
  };

  const textSizeClasses = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg'
  };

  return (
    <div className="flex items-center justify-center h-64" data-name="loading-spinner">
      <div className="flex flex-col items-center gap-3">
        <div
          className={`animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 dark:border-gray-700 dark:border-t-blue-400 ${sizeClasses[size]}`}
        />
        <div className={`text-gray-500 dark:text-gray-400 ${textSizeClasses[size]}`}>
          {resolvedMessage}
        </div>
      </div>
    </div>
  );
};
