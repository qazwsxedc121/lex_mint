/**
 * ProjectExplorer - Main project view with file tree and viewer
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useOutletContext, useNavigate } from 'react-router-dom';
import { ProjectSelector } from './components/ProjectSelector';
import { FileTree } from './components/FileTree';
import { FileViewer } from './components/FileViewer';
import { useFileTree } from './hooks/useFileTree';
import { useFileContent } from './hooks/useFileContent';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import ProjectChatSidebar from './components/ProjectChatSidebar';
import { ProjectEditorContext } from './contexts/ProjectEditorContext';
import type { Project } from '../../types/project';
import { ChatComposerProvider, ChatServiceProvider } from '../../shared/chat';
import type { ChatNavigation } from '../../shared/chat';
import { createProjectChatAPI } from './services/projectChatAPI';
import { createFile, createFolder, deleteFile, deleteFolder, readFile, renameProjectPath } from '../../services/api';

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
    getCurrentFile,
    setCurrentProject,
    setCurrentFile,
    getProjectSession,
    setProjectSession,
    chatSidebarOpen,
    toggleChatSidebar,
    fileTreeOpen,
    toggleFileTree
  } = useProjectWorkspaceStore();

  // Get current file path for this project
  const currentFilePath = projectId ? getCurrentFile(projectId) : null;
  const savedSessionId = projectId ? getProjectSession(projectId) : null;

  // Local state for selected file
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(currentFilePath);

  // State for editor actions (used by context)
  const [editorActions, setEditorActions] = useState<{ insertContent: (text: string) => void } | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  // Find current project
  const currentProject = projects.find(p => p.id === projectId);

  // On mount: If no projectId in URL but we have a saved one, navigate to it
  useEffect(() => {
    if (!projectId && currentProjectId && projects.some(p => p.id === currentProjectId)) {
      navigate(`/projects/${currentProjectId}`, { replace: true });
    }
  }, [projectId, currentProjectId, projects, navigate]);

  // When projectId changes, update the store and clear selection
  useEffect(() => {
    if (projectId && projectId !== currentProjectId) {
      setCurrentProject(projectId);
      setSelectedFilePath(null);
      // Clear the stored file path for this project to prevent loading non-existent files
      setCurrentFile(projectId, null);
    }
  }, [projectId, currentProjectId, setCurrentProject, setCurrentFile]);

  // Restore file selection from store when switching back to a project
  useEffect(() => {
    if (projectId && currentFilePath && !selectedFilePath) {
      setSelectedFilePath(currentFilePath);
    }
  }, [projectId, currentFilePath, selectedFilePath]);

  // Reset current session when project changes
  useEffect(() => {
    setCurrentSessionId(null);
  }, [projectId]);

  // Load file tree
  const { tree, loading: treeLoading, error: treeError, refreshTree } = useFileTree(projectId || null);

  // Load file content when a file is selected
  const { content, loading: contentLoading, error: contentError } = useFileContent(
    projectId || null,
    selectedFilePath
  );

  const handleFileSelect = (path: string) => {
    setSelectedFilePath(path);
    // Save to store immediately when user selects a file
    if (projectId) {
      setCurrentFile(projectId, path);
    }
  };

  const handleCreateFile = useCallback(async (directoryPath: string, filename: string) => {
    if (!projectId) {
      throw new Error('Project ID is required');
    }
    const normalizedDirectory = directoryPath ? directoryPath.replace(/\\/g, '/') : '';
    const filePath = normalizedDirectory ? `${normalizedDirectory}/${filename}` : filename;
    const created = await createFile(projectId, filePath, '');
    await refreshTree();
    return created.path;
  }, [projectId, refreshTree]);

  const handleCreateFolder = useCallback(async (directoryPath: string, folderName: string) => {
    if (!projectId) {
      throw new Error('Project ID is required');
    }
    const normalizedDirectory = directoryPath ? directoryPath.replace(/\\/g, '/') : '';
    const folderPath = normalizedDirectory ? `${normalizedDirectory}/${folderName}` : folderName;
    await createFolder(projectId, folderPath);
    await refreshTree();
    return folderPath;
  }, [projectId, refreshTree]);

  const handleDuplicateFile = useCallback(async (filePath: string, newFileName: string) => {
    if (!projectId) {
      throw new Error('Project ID is required');
    }
    const normalizedPath = filePath.replace(/\\/g, '/');
    const lastSlash = normalizedPath.lastIndexOf('/');
    const directory = lastSlash > -1 ? normalizedPath.slice(0, lastSlash) : '';
    const newPath = directory ? `${directory}/${newFileName}` : newFileName;
    const existing = await readFile(projectId, normalizedPath);
    const created = await createFile(projectId, newPath, existing.content, existing.encoding);
    await refreshTree();
    return created.path;
  }, [projectId, refreshTree]);

  const handleDeleteFile = useCallback(async (filePath: string) => {
    if (!projectId) {
      throw new Error('Project ID is required');
    }
    await deleteFile(projectId, filePath);
    await refreshTree();
    if (selectedFilePath === filePath) {
      setSelectedFilePath(null);
      setCurrentFile(projectId, null);
    }
  }, [projectId, refreshTree, selectedFilePath, setCurrentFile, setSelectedFilePath]);

  const handleDeleteFolder = useCallback(async (directoryPath: string) => {
    if (!projectId) {
      throw new Error('Project ID is required');
    }
    await deleteFolder(projectId, directoryPath, true);
    await refreshTree();
    if (selectedFilePath && (selectedFilePath === directoryPath || selectedFilePath.startsWith(`${directoryPath}/`))) {
      setSelectedFilePath(null);
      setCurrentFile(projectId, null);
    }
  }, [projectId, refreshTree, selectedFilePath, setCurrentFile, setSelectedFilePath]);

  const handleRenamePath = useCallback(async (sourcePath: string, targetPath: string) => {
    if (!projectId) {
      throw new Error('Project ID is required');
    }
    const normalizedSource = sourcePath.replace(/\\/g, '/');
    const normalizedTarget = targetPath.replace(/\\/g, '/');
    const result = await renameProjectPath(projectId, normalizedSource, normalizedTarget);
    const newPath = result.new_path || normalizedTarget;
    await refreshTree();

    if (selectedFilePath) {
      const normalizedSelected = selectedFilePath.replace(/\\/g, '/');
      if (normalizedSelected === normalizedSource) {
        setSelectedFilePath(newPath);
        setCurrentFile(projectId, newPath);
      } else if (normalizedSelected.startsWith(`${normalizedSource}/`)) {
        const updatedPath = `${newPath}${normalizedSelected.slice(normalizedSource.length)}`;
        setSelectedFilePath(updatedPath);
        setCurrentFile(projectId, updatedPath);
      }
    }

    return newPath;
  }, [projectId, refreshTree, selectedFilePath, setCurrentFile, setSelectedFilePath]);

  // Create context value for editor actions
  const editorContextValue = useMemo(() => ({
    insertToEditor: (content: string) => {
      editorActions?.insertContent(content);
    },
    isEditorAvailable: editorActions !== null && content !== null,
  }), [editorActions, content]);

  const handleSetCurrentSessionId = useCallback((sessionId: string | null) => {
    setCurrentSessionId(sessionId);
    if (projectId) {
      setProjectSession(projectId, sessionId);
    }
  }, [projectId, setProjectSession]);

  const projectChatAPI = useMemo(() => {
    return projectId ? createProjectChatAPI(projectId) : null;
  }, [projectId]);

  const navigation: ChatNavigation | undefined = useMemo(() => {
    if (!projectId) return undefined;
    return {
      navigateToSession: (id: string) => handleSetCurrentSessionId(id),
      navigateToRoot: () => {
        // No-op: already in project view
      },
      getCurrentSessionId: () => currentSessionId,
    };
  }, [projectId, currentSessionId, handleSetCurrentSessionId]);

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

  if (!projectChatAPI || !navigation) {
    return null;
  }

  return (
    <ChatServiceProvider api={projectChatAPI} navigation={navigation}>
      <ChatComposerProvider>
        <ProjectEditorContext.Provider value={editorContextValue}>
          <div data-name="project-explorer-root" className="flex flex-1 overflow-hidden min-w-0">
            {/* Left: File Tree */}
            {fileTreeOpen && (
              <div data-name="file-tree-panel" className="w-[300px] flex-shrink-0 flex flex-col border-r border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800">
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
                  onCreateFile={handleCreateFile}
                  onCreateFolder={handleCreateFolder}
                  onDuplicateFile={handleDuplicateFile}
                  onDeleteFile={handleDeleteFile}
                  onDeleteFolder={handleDeleteFolder}
                  onRenamePath={handleRenamePath}
                />
              </div>
            </div>
            )}

            {/* Center: File Viewer */}
            <div data-name="file-viewer-panel" className="flex-1 min-w-0 flex flex-col">
              <FileViewer
                projectId={projectId}
                projectName={currentProject?.name || 'Project'}
                content={content}
                loading={contentLoading}
                error={contentError}
                chatSidebarOpen={chatSidebarOpen}
                fileTreeOpen={fileTreeOpen}
                onToggleChatSidebar={toggleChatSidebar}
                onToggleFileTree={toggleFileTree}
                onEditorReady={setEditorActions}
              />
            </div>

            {/* Right: Chat Sidebar (collapsible) */}
            {chatSidebarOpen && (
              <div data-name="chat-sidebar-container" className="w-[600px] flex-shrink-0 flex flex-col h-full min-h-0 overflow-hidden border-l border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900">
                <ProjectChatSidebar
                  projectId={projectId}
                  currentSessionId={currentSessionId}
                  savedSessionId={savedSessionId}
                  onSetCurrentSessionId={handleSetCurrentSessionId}
                />
              </div>
            )}
          </div>
        </ProjectEditorContext.Provider>
      </ChatComposerProvider>
    </ChatServiceProvider>
  );
};
