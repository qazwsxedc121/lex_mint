/**
 * ProjectsWelcome - Welcome screen shown when no project is selected
 */

import React, { useEffect } from 'react';
import { useOutletContext, useNavigate } from 'react-router-dom';
import { FolderIcon } from '@heroicons/react/24/outline';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import type { Project } from '../../types/project';

interface ProjectsOutletContext {
  projects: Project[];
  onManageClick: () => void;
}

export const ProjectsWelcome: React.FC = () => {
  const { projects, onManageClick } = useOutletContext<ProjectsOutletContext>();
  const navigate = useNavigate();
  const { currentProjectId, setCurrentProject } = useProjectWorkspaceStore();

  // Auto-restore last opened project on mount
  useEffect(() => {
    if (currentProjectId && projects.some(p => p.id === currentProjectId)) {
      navigate(`/projects/${currentProjectId}`, { replace: true });
    }
  }, [currentProjectId, projects, navigate]);

  const handleProjectSelect = (projectId: string) => {
    setCurrentProject(projectId);
    navigate(`/projects/${projectId}`);
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 bg-white dark:bg-gray-900">
      <FolderIcon className="h-24 w-24 text-gray-400 dark:text-gray-600 mb-4" />
      <h2 className="text-2xl font-medium text-gray-900 dark:text-white mb-2">
        Select a Project
      </h2>
      <p className="text-gray-500 dark:text-gray-400 mb-6 text-center max-w-md">
        Choose a project to browse files, or create a new one.
      </p>

      {/* Project List */}
      {projects.length > 0 ? (
        <div className="w-full max-w-md space-y-2 mb-6">
          {projects.map((project) => (
            <button
              key={project.id}
              onClick={() => handleProjectSelect(project.id)}
              className="w-full p-4 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-left"
            >
              <div className="font-medium text-gray-900 dark:text-white">
                {project.name}
              </div>
              {project.description && (
                <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {project.description}
                </div>
              )}
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
                {project.root_path}
              </div>
            </button>
          ))}
        </div>
      ) : (
        <p className="text-gray-500 dark:text-gray-400 mb-6">
          No projects available
        </p>
      )}

      {/* Manage Projects Button */}
      <button
        onClick={onManageClick}
        className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
      >
        Manage Projects
      </button>
    </div>
  );
};
