/**
 * StatusBadge Component
 *
 * Displays an enabled/disabled status badge.
 */

import React from 'react';

interface StatusBadgeProps {
  /** Whether the item is enabled */
  enabled: boolean;
  /** Custom enabled label */
  enabledLabel?: string;
  /** Custom disabled label */
  disabledLabel?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  enabled,
  enabledLabel = 'Enabled',
  disabledLabel = 'Disabled'
}) => {
  return (
    <span
      data-name="status-badge"
      className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
        enabled
          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
          : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
      }`}
    >
      {enabled ? enabledLabel : disabledLabel}
    </span>
  );
};
