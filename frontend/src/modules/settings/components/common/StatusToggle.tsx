/**
 * StatusToggle Component
 *
 * Inline toggle switch for enabled/disabled status in tables.
 */

import React from 'react';

interface StatusToggleProps {
  /** Whether the item is enabled */
  enabled: boolean;
  /** Toggle handler */
  onToggle: () => void;
  /** Whether the toggle is processing */
  loading?: boolean;
}

export const StatusToggle: React.FC<StatusToggleProps> = ({
  enabled,
  onToggle,
  loading = false
}) => {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      disabled={loading}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      data-name="status-toggle"
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800 disabled:opacity-50 disabled:cursor-not-allowed ${
        enabled
          ? 'bg-blue-600'
          : 'bg-gray-300 dark:bg-gray-600'
      }`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform duration-200 ${
          enabled ? 'translate-x-[18px]' : 'translate-x-[3px]'
        }`}
      />
    </button>
  );
};
