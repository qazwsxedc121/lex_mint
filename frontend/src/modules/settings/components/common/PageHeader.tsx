/**
 * PageHeader Component
 *
 * Displays page title, description, and action buttons.
 */

import React from 'react';

interface PageHeaderProps {
  /** Page title */
  title: string;
  /** Optional description */
  description?: string;
  /** Action buttons */
  actions?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  actions
}) => {
  return (
    <div className="flex justify-between items-start mb-6" data-name="page-header">
      <div>
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
          {title}
        </h3>
        {description && (
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2">
          {actions}
        </div>
      )}
    </div>
  );
};
