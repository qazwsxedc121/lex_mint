/**
 * BackendDirectoryPicker - Select server-side directories for project roots
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Modal } from '../../settings/components/common/Modal';
import { FolderIcon, ArrowUturnLeftIcon, PlusIcon } from '@heroicons/react/24/outline';
import type { DirectoryEntry } from '../../../types/project';
import { createProjectBrowseDirectory, listProjectBrowseRoots, listProjectDirectories } from '../../../services/api';

interface BackendDirectoryPickerProps {
  isOpen: boolean;
  initialPath?: string;
  onClose: () => void;
  onSelect: (path: string) => void;
}

const resolveParentPath = (path: string) => {
  const trimmed = path.replace(/[\\/]+$/, '');
  const separator = trimmed.includes('\\') ? '\\' : '/';
  const lastIndex = trimmed.lastIndexOf(separator);
  if (lastIndex <= 0) {
    return trimmed;
  }
  return trimmed.slice(0, lastIndex);
};

export const BackendDirectoryPicker: React.FC<BackendDirectoryPickerProps> = ({
  isOpen,
  initialPath,
  onClose,
  onSelect,
}) => {
  const [roots, setRoots] = useState<DirectoryEntry[]>([]);
  const [entries, setEntries] = useState<DirectoryEntry[]>([]);
  const [currentRoot, setCurrentRoot] = useState<string | null>(null);
  const [currentPath, setCurrentPath] = useState<string | null>(null);
  const [newFolderName, setNewFolderName] = useState('');
  const [loading, setLoading] = useState(false);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canGoUp = useMemo(() => {
    if (!currentPath || !currentRoot) return false;
    return currentPath !== currentRoot;
  }, [currentPath, currentRoot]);

  const loadRoots = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listProjectBrowseRoots();
      setRoots(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load roots';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const loadDirectories = async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listProjectDirectories(path);
      setEntries(data);
      setCurrentPath(path);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load directories';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    setRoots([]);
    setEntries([]);
    setCurrentRoot(null);
    setCurrentPath(null);
    setNewFolderName('');
    void loadRoots();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || roots.length === 0 || !initialPath) {
      return;
    }
    const matched = roots.find((root) => initialPath.startsWith(root.path));
    if (matched) {
      setCurrentRoot(matched.path);
      void loadDirectories(initialPath);
    }
  }, [initialPath, isOpen, roots]);

  const handleRootSelect = (path: string) => {
    setCurrentRoot(path);
    setNewFolderName('');
    void loadDirectories(path);
  };

  const handleUp = () => {
    if (!currentPath || !currentRoot) return;
    const parent = resolveParentPath(currentPath);
    if (parent === currentPath || parent.length < currentRoot.length) {
      return;
    }
    setNewFolderName('');
    void loadDirectories(parent);
  };

  const handleEnter = (entry: DirectoryEntry) => {
    if (!entry.is_dir) return;
    setNewFolderName('');
    void loadDirectories(entry.path);
  };

  const handleCreateFolder = async () => {
    if (!currentPath || loading || creatingFolder) {
      return;
    }

    const trimmedName = newFolderName.trim();
    if (!trimmedName) {
      setError('Folder name is required');
      return;
    }

    setCreatingFolder(true);
    setError(null);
    try {
      const created = await createProjectBrowseDirectory(currentPath, trimmedName);
      setNewFolderName('');
      await loadDirectories(created.path);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create folder';
      setError(message);
    } finally {
      setCreatingFolder(false);
    }
  };

  const handleChoose = () => {
    if (currentPath) {
      onSelect(currentPath);
      onClose();
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Select Server Directory"
      size="lg"
    >
      <div className="space-y-4" data-name="backend-directory-picker">
        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
            {error}
          </div>
        )}

        {currentRoot ? (
          <div className="space-y-3" data-name="backend-directory-browser">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm text-gray-600 dark:text-gray-300 truncate">
                {currentPath || currentRoot}
              </div>
              <button
                type="button"
                onClick={handleUp}
                disabled={!canGoUp || loading || creatingFolder}
                className="inline-flex items-center gap-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50"
              >
                <ArrowUturnLeftIcon className="h-4 w-4" />
                Up
              </button>
            </div>

            <div className="flex items-center gap-2" data-name="backend-directory-create">
              <input
                type="text"
                value={newFolderName}
                onChange={(event) => setNewFolderName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    void handleCreateFolder();
                  }
                }}
                disabled={loading || creatingFolder}
                placeholder="New folder name"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-60"
              />
              <button
                type="button"
                onClick={() => {
                  void handleCreateFolder();
                }}
                disabled={!currentPath || loading || creatingFolder || newFolderName.trim().length === 0}
                className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-60"
              >
                <PlusIcon className="h-4 w-4" />
                {creatingFolder ? 'Creating...' : 'Create'}
              </button>
            </div>

            <div className="max-h-72 overflow-y-auto rounded-md border border-gray-200 dark:border-gray-700" data-name="backend-directory-list">
              {loading ? (
                <div className="px-3 py-4 text-sm text-gray-500 dark:text-gray-400">
                  Loading directories...
                </div>
              ) : entries.length === 0 ? (
                <div className="px-3 py-4 text-sm text-gray-500 dark:text-gray-400">
                  No subdirectories
                </div>
              ) : (
                entries.map((entry) => (
                  <button
                    key={entry.path}
                    type="button"
                    onClick={() => handleEnter(entry)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700"
                  >
                    <FolderIcon className="h-4 w-4 text-gray-400" />
                    <span className="truncate">{entry.name}</span>
                  </button>
                ))
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-2" data-name="backend-root-list">
            <div className="text-sm text-gray-600 dark:text-gray-300">
              Choose a root folder to browse:
            </div>
            {loading ? (
              <div className="text-sm text-gray-500 dark:text-gray-400">Loading roots...</div>
            ) : roots.length === 0 ? (
              <div className="text-sm text-gray-500 dark:text-gray-400">No roots configured.</div>
            ) : (
              roots.map((root) => (
                <button
                  key={root.path}
                  type="button"
                  onClick={() => handleRootSelect(root.path)}
                  className="flex w-full items-center gap-2 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  <FolderIcon className="h-4 w-4 text-gray-400" />
                  <span className="truncate">{root.path}</span>
                </button>
              ))
            )}
          </div>
        )}

        <div className="flex items-center justify-end gap-3 pt-2" data-name="backend-directory-actions">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleChoose}
            disabled={!currentPath}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-60"
          >
            Use this folder
          </button>
        </div>
      </div>
    </Modal>
  );
};
