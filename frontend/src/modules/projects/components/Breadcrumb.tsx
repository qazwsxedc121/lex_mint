/**
 * Breadcrumb - File path breadcrumb component
 */

import React from 'react';
import { ChevronRightIcon, ClipboardDocumentIcon } from '@heroicons/react/24/outline';

interface BreadcrumbProps {
  projectName: string;
  filePath: string;
}

export const Breadcrumb: React.FC<BreadcrumbProps> = ({ projectName, filePath }) => {
  const pathSegments = filePath.split(/[/\\]/).filter(Boolean);

  const handleCopyPath = () => {
    navigator.clipboard.writeText(filePath);
  };

  return (
    <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 overflow-x-auto min-w-0 flex-1">
      <span className="font-medium text-gray-900 dark:text-white flex-shrink-0">
        {projectName}
      </span>
      {pathSegments.map((segment, index) => (
        <React.Fragment key={index}>
          <ChevronRightIcon className="h-4 w-4 flex-shrink-0" />
          <span className={index === pathSegments.length - 1 ? 'text-gray-900 dark:text-white font-medium' : ''}>
            {segment}
          </span>
        </React.Fragment>
      ))}
      <button
        onClick={handleCopyPath}
        className="ml-2 p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 flex-shrink-0"
        title="Copy full path"
      >
        <ClipboardDocumentIcon className="h-4 w-4" />
      </button>
    </div>
  );
};
