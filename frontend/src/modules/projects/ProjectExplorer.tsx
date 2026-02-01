/**
 * ProjectExplorer - Main project view with file tree and viewer
 */

import React, { useState, useEffect } from 'react';
import { useParams, useOutletContext, useNavigate } from 'react-router-dom';
import { ProjectSelector } from './components/ProjectSelector';
import { FileTree } from './components/FileTree';
import { FileViewer } from './components/FileViewer';
import { useFileTree } from './hooks/useFileTree';
import { useFileContent } from './hooks/useFileContent';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import ProjectChatSidebar from './components/ProjectChatSidebar';
import type { Project } from '../../types/project';

interface ProjectsOutletContext {
  projects: Project[];
  onManageClick: () => void;
}

export const ProjectExplorer: React.FC = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { projects, onManageClick } = useOutletContext<ProjectsOutletContext>();

  // Get workspace state from global store
  const {
    currentProjectId,
    currentFilePath,
    setCurrentProject,
    setCurrentFile,
    chatSidebarOpen,
    toggleChatSidebar
  } = useProjectWorkspaceStore();

  // Local state for selected file
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(currentFilePath);

  // Find current project
  const currentProject = projects.find(p => p.id === projectId);

  // On mount: If no projectId in URL but we have a saved one, navigate to it
  useEffect(() => {
    if (!projectId && currentProjectId && projects.some(p => p.id === currentProjectId)) {
      navigate(`/projects/${currentProjectId}`, { replace: true });
    }
  }, [projectId, currentProjectId, projects, navigate]);

  // When projectId changes, update the store
  useEffect(() => {
    if (projectId && projectId !== currentProjectId) {
      setCurrentProject(projectId);
    }
  }, [projectId, currentProjectId, setCurrentProject]);

  // When file selection changes, update the store
  useEffect(() => {
    if (selectedFilePath !== currentFilePath) {
      setCurrentFile(selectedFilePath);
    }
  }, [selectedFilePath, currentFilePath, setCurrentFile]);

  // Restore file selection from store when component mounts or project changes
  useEffect(() => {
    if (projectId === currentProjectId && currentFilePath && !selectedFilePath) {
      setSelectedFilePath(currentFilePath);
    }
  }, [projectId, currentProjectId, currentFilePath, selectedFilePath]);

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
    <div className="flex overflow-hidden min-w-0">
      {/* Left: File Tree */}
      <div className="w-[300px] flex-shrink-0 flex flex-col border-r border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800">
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

      {/* Center: File Viewer */}
      <div className="flex-1 min-w-0 flex flex-col">
        <FileViewer
          projectId={projectId}
          projectName={currentProject?.name || 'Project'}
          content={content}
          loading={contentLoading}
          error={contentError}
          chatSidebarOpen={chatSidebarOpen}
          onToggleChatSidebar={toggleChatSidebar}
        />
      </div>

      {/* Right: Chat Sidebar (collapsible) */}
      {chatSidebarOpen && (
        <div className="w-[400px] flex-shrink-0 flex flex-col border-l border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900">
          <ProjectChatSidebar projectId={projectId} />
        </div>
      )}
    </div>
  );
};
