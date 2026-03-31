import { ArrowPathIcon, ChevronDoubleLeftIcon, ChevronDoubleRightIcon } from '@heroicons/react/24/outline';
import { Breadcrumb } from './Breadcrumb';

interface FileViewerBreadcrumbBarProps {
  projectName: string;
  filePath?: string;
  fileTreeOpen: boolean;
  onToggleFileTree: () => void;
  refreshTitle: string;
  refreshDisabled: boolean;
  refreshingProject: boolean;
  onRefreshProject: () => void;
  toggleTreeTitle: string;
}

export const FileViewerBreadcrumbBar = ({
  projectName,
  filePath,
  fileTreeOpen,
  onToggleFileTree,
  refreshTitle,
  refreshDisabled,
  refreshingProject,
  onRefreshProject,
  toggleTreeTitle,
}: FileViewerBreadcrumbBarProps) => (
  <div data-name="file-viewer-breadcrumb-bar" className="border-b border-gray-300 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800">
    <div data-name="file-viewer-breadcrumb-row" className="flex items-center gap-2 min-w-0">
      <button
        type="button"
        title={toggleTreeTitle}
        aria-pressed={fileTreeOpen}
        onClick={onToggleFileTree}
        data-name="file-tree-toggle"
        className={`p-1.5 rounded ${
          fileTreeOpen
            ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
            : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
        }`}
      >
        {fileTreeOpen ? (
          <ChevronDoubleLeftIcon className="h-4 w-4" />
        ) : (
          <ChevronDoubleRightIcon className="h-4 w-4" />
        )}
      </button>
      <div className="min-w-0 flex-1">
        {filePath ? (
          <Breadcrumb projectName={projectName} filePath={filePath} />
        ) : (
          <div data-name="file-viewer-breadcrumb-placeholder" className="text-sm text-gray-600 dark:text-gray-400 font-medium">
            {projectName}
          </div>
        )}
      </div>
      <button
        type="button"
        title={refreshTitle}
        aria-label={refreshTitle}
        onClick={onRefreshProject}
        disabled={refreshDisabled}
        data-name="project-refresh-button"
        className={`p-1.5 rounded ${
          refreshDisabled
            ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed opacity-60'
            : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
        }`}
      >
        <ArrowPathIcon className={`h-4 w-4 ${refreshingProject ? 'animate-spin' : ''}`} />
      </button>
    </div>
  </div>
);
