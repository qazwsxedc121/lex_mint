/**
 * ProjectExplorer - Main project view with file tree and viewer
 */

import React, { useState } from 'react';
import { useParams, useOutletContext } from 'react-router-dom';
import { ProjectSelector } from './components/ProjectSelector';
import { FileTree } from './components/FileTree';
import { FileViewer } from './components/FileViewer';
import { useFileTree } from './hooks/useFileTree';
import { useFileContent } from './hooks/useFileContent';
import type { Project } from '../../types/project';

interface ProjectsOutletContext {
  projects: Project[];
  onManageClick: () => void;
}

export const ProjectExplorer: React.FC = () => {
  const { projectId } = useParams();
  const { projects, onManageClick } = useOutletContext<ProjectsOutletContext>();
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);

  // Find current project
  const currentProject = projects.find(p => p.id === projectId);

  // Load file tree
  const { tree, loading: treeLoading, error: treeError } = useFileTree(projectId || null);

  // Load file content when a file is selected
  const { content, loading: contentLoading, error: contentError } = useFileContent(
    projectId || null,
    selectedFilePath
  );

  const handleFileSelect = (path: string) => {
    setSelectedFilePath(path);
  };

  if (!projectId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white dark:bg-gray-900">
        <p className="text-gray-500 dark:text-gray-400">Invalid project ID</p>
      </div>
    );
  }

  if (treeLoading && !tree) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden">
        <ProjectSelector
          projects={projects}
          currentProject={currentProject}
          onManageClick={onManageClick}
        />
        <div className="flex-1 flex items-center justify-center bg-white dark:bg-gray-900">
          <p className="text-gray-500 dark:text-gray-400">Loading project...</p>
        </div>
      </div>
    );
  }

  if (treeError) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden">
        <ProjectSelector
          projects={projects}
          currentProject={currentProject}
          onManageClick={onManageClick}
        />
        <div className="flex-1 flex items-center justify-center bg-white dark:bg-gray-900">
          <div className="text-center">
            <p className="text-red-600 dark:text-red-400 mb-2">Failed to load project</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">{treeError}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!tree) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden">
        <ProjectSelector
          projects={projects}
          currentProject={currentProject}
          onManageClick={onManageClick}
        />
        <div className="flex-1 flex items-center justify-center bg-white dark:bg-gray-900">
          <p className="text-gray-500 dark:text-gray-400">No files found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* File Tree Column */}
      <div className="w-[300px] flex-shrink-0 flex flex-col border-r border-gray-300 dark:border-gray-700">
        <ProjectSelector
          projects={projects}
          currentProject={currentProject}
          onManageClick={onManageClick}
        />
        <div className="flex-1 overflow-hidden">
          <FileTree
            tree={tree}
            selectedPath={selectedFilePath}
            onFileSelect={handleFileSelect}
          />
        </div>
      </div>

      {/* File Viewer Column */}
      <FileViewer
        projectName={currentProject?.name || 'Project'}
        content={content}
        loading={contentLoading}
        error={contentError}
      />
    </div>
  );
};
