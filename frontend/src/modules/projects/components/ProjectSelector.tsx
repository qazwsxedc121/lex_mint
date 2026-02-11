/**
 * ProjectSelector - Dropdown for selecting projects
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDownIcon, CogIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { useProjectWorkspaceStore } from '../../../stores/projectWorkspaceStore';
import type { Project } from '../../../types/project';

interface ProjectSelectorProps {
  projects: Project[];
  currentProject: Project | undefined;
  onManageClick: () => void;
  onCloseProject: () => void;
}

export const ProjectSelector: React.FC<ProjectSelectorProps> = ({
  projects,
  currentProject,
  onManageClick,
  onCloseProject,
}) => {
  const navigate = useNavigate();
  const { setCurrentProject } = useProjectWorkspaceStore();
  const [isOpen, setIsOpen] = React.useState(false);

  const handleProjectSelect = (projectId: string) => {
    setCurrentProject(projectId);
    navigate(`/projects/${projectId}`);
    setIsOpen(false);
  };

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = () => setIsOpen(false);
    if (isOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [isOpen]);

  return (
    <div className="border-b border-gray-300 dark:border-gray-700 p-3 bg-gray-50 dark:bg-gray-800">
      <div className="flex gap-2">
        {/* Project Dropdown */}
        <div className="relative flex-1">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setIsOpen(!isOpen);
            }}
            className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md text-left text-sm text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors flex items-center justify-between"
          >
            <span className="truncate">
              {currentProject ? currentProject.name : 'Select Project'}
            </span>
            <ChevronDownIcon className="h-4 w-4 ml-2 flex-shrink-0 text-gray-500 dark:text-gray-400" />
          </button>

          {/* Dropdown Menu */}
          {isOpen && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md shadow-lg z-10 max-h-64 overflow-y-auto">
              {projects.length === 0 ? (
                <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400 text-center">
                  No projects available
                </div>
              ) : (
                projects.map((project) => (
                  <button
                    key={project.id}
                    onClick={() => handleProjectSelect(project.id)}
                    className={`w-full px-3 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors ${
                      currentProject?.id === project.id
                        ? 'bg-blue-50 dark:bg-blue-900 text-blue-600 dark:text-blue-300'
                        : 'text-gray-900 dark:text-white'
                    }`}
                  >
                    <div className="font-medium truncate">{project.name}</div>
                    {project.description && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {project.description}
                      </div>
                    )}
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* Manage Button */}
        <button
          onClick={onManageClick}
          className="px-3 py-2 bg-gray-200 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
          title="Manage Projects"
          aria-label="Manage Projects"
        >
          <CogIcon className="h-5 w-5 text-gray-600 dark:text-gray-300" />
        </button>

        {/* Close Current Project Button */}
        <button
          onClick={onCloseProject}
          className="px-3 py-2 bg-gray-200 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
          title="Close Current Project"
          aria-label="Close current project"
        >
          <XMarkIcon className="h-5 w-5 text-gray-600 dark:text-gray-300" />
        </button>
      </div>

      {/* Current Project Path */}
      {currentProject && (
        <div className="mt-2 text-xs text-gray-500 dark:text-gray-400 truncate">
          {currentProject.root_path}
        </div>
      )}
    </div>
  );
};
