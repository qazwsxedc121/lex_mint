import React from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import type { ProjectNoticeState } from '../hooks/useProjectNotice';

interface ProjectNoticeProps {
  notice: ProjectNoticeState | null;
  onDismiss: () => void;
}

export const ProjectNotice: React.FC<ProjectNoticeProps> = ({ notice, onDismiss }) => {
  if (!notice) {
    return null;
  }

  const colorClassName = notice.level === 'error'
    ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200'
    : notice.level === 'success'
    ? 'border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-900/20 dark:text-green-200'
    : 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-200';

  return (
    <div
      data-name="project-notice"
      className={`mx-4 mt-3 rounded-md border px-3 py-2 text-sm flex items-start gap-2 ${colorClassName}`}
      role="status"
      aria-live="polite"
    >
      <div className="flex-1">{notice.message}</div>
      <button
        type="button"
        onClick={onDismiss}
        className="rounded p-0.5 hover:bg-black/10 dark:hover:bg-white/10"
        aria-label="Dismiss notice"
      >
        <XMarkIcon className="h-4 w-4" />
      </button>
    </div>
  );
};
