/**
 * FileTree - Recursive file tree component
 */

import React, { useEffect, useRef, useState } from 'react';
import { FolderIcon, FolderOpenIcon, DocumentIcon, ChevronRightIcon, ChevronDownIcon, PlusIcon } from '@heroicons/react/24/outline';
import type { FileNode } from '../../../types/project';

interface FileTreeProps {
  tree: FileNode;
  selectedPath: string | null;
  onFileSelect: (path: string) => void;
  onCreateFile?: (directoryPath: string, filename: string) => Promise<string>;
  level?: number;
}

interface FileTreeItemProps {
  tree: FileNode;
  selectedPath: string | null;
  onFileSelect: (path: string) => void;
  level: number;
  onCreateRequest?: (directoryPath: string, directoryName: string) => void;
  allowCreate: boolean;
}

const FileTreeItem: React.FC<FileTreeItemProps> = ({
  tree,
  selectedPath,
  onFileSelect,
  level,
  onCreateRequest,
  allowCreate,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const isDirectory = tree.type === 'directory';
  const isSelected = selectedPath === tree.path;

  const handleClick = () => {
    if (isDirectory) {
      setIsExpanded(!isExpanded);
    } else {
      onFileSelect(tree.path);
    }
  };

  const handleCreateClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (isDirectory && !isExpanded) {
      setIsExpanded(true);
    }
    onCreateRequest?.(tree.path, tree.name);
  };

  return (
    <div>
      <div
        className={`group flex items-center py-1 px-2 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors ${
          isSelected ? 'bg-blue-100 dark:bg-blue-900' : ''
        }`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={handleClick}
      >
        {isDirectory ? (
          <>
            {isExpanded ? (
              <ChevronDownIcon className="h-4 w-4 text-gray-500 dark:text-gray-400 mr-1 flex-shrink-0" />
            ) : (
              <ChevronRightIcon className="h-4 w-4 text-gray-500 dark:text-gray-400 mr-1 flex-shrink-0" />
            )}
            {isExpanded ? (
              <FolderOpenIcon className="h-4 w-4 text-blue-500 dark:text-blue-400 mr-2 flex-shrink-0" />
            ) : (
              <FolderIcon className="h-4 w-4 text-blue-500 dark:text-blue-400 mr-2 flex-shrink-0" />
            )}
          </>
        ) : (
          <>
            <span className="w-4 mr-1 flex-shrink-0" />
            <DocumentIcon className="h-4 w-4 text-gray-500 dark:text-gray-400 mr-2 flex-shrink-0" />
          </>
        )}
        <span className="text-sm text-gray-900 dark:text-white truncate">
          {tree.name}
        </span>
        {isDirectory && allowCreate && (
          <button
            type="button"
            onClick={handleCreateClick}
            className="ml-auto p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:text-gray-500 dark:hover:text-gray-300 dark:hover:bg-gray-700 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity"
            title="New file"
          >
            <PlusIcon className="h-4 w-4" />
          </button>
        )}
      </div>

      {isDirectory && isExpanded && tree.children && (
        <div>
          {tree.children.map((child) => (
            <FileTreeItem
              key={child.path}
              tree={child}
              selectedPath={selectedPath}
              onFileSelect={onFileSelect}
              level={level + 1}
              onCreateRequest={onCreateRequest}
              allowCreate={allowCreate}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const FileTree: React.FC<Omit<FileTreeProps, 'level'>> = ({
  tree,
  selectedPath,
  onFileSelect,
  onCreateFile,
}) => {
  const [createTarget, setCreateTarget] = useState<{ directoryPath: string; directoryName: string } | null>(null);
  const [newFileName, setNewFileName] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const allowCreate = Boolean(onCreateFile);

  useEffect(() => {
    if (!createTarget) return undefined;
    const timer = window.setTimeout(() => {
      inputRef.current?.focus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [createTarget]);

  const handleOpenCreate = (directoryPath: string, directoryName: string) => {
    setCreateTarget({ directoryPath, directoryName });
    setNewFileName('');
    setCreateError(null);
  };

  const handleCloseCreate = () => {
    setCreateTarget(null);
    setNewFileName('');
    setCreateError(null);
    setCreating(false);
  };

  const handleCreateSubmit = async () => {
    if (!onCreateFile || !createTarget || creating) return;
    const trimmedName = newFileName.trim();
    if (!trimmedName) {
      setCreateError('Please enter a file name.');
      return;
    }
    if (/[\\/]/.test(trimmedName)) {
      setCreateError('File name cannot contain / or \\\\.');
      return;
    }

    setCreating(true);
    setCreateError(null);
    try {
      const createdPath = await onCreateFile(createTarget.directoryPath, trimmedName);
      handleCloseCreate();
      onFileSelect(createdPath);
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to create file.';
      setCreateError(message);
      setCreating(false);
    }
  };

  return (
    <div data-name="file-tree" className="h-full overflow-y-auto bg-white dark:bg-gray-800 border-r border-gray-300 dark:border-gray-700">
      <FileTreeItem
        tree={tree}
        selectedPath={selectedPath}
        onFileSelect={onFileSelect}
        level={0}
        onCreateRequest={allowCreate ? handleOpenCreate : undefined}
        allowCreate={allowCreate}
      />
      {createTarget && (
        <div data-name="file-create-modal" className="fixed inset-0 z-50 overflow-y-auto">
          <div
            className="fixed inset-0 bg-black bg-opacity-50"
            onClick={handleCloseCreate}
          />
          <div className="flex min-h-full items-center justify-center p-4">
            <div data-name="file-create-modal-card" className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-1">
                New File
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
                Create in {createTarget.directoryName}
              </p>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  handleCreateSubmit();
                }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    File Name
                  </label>
                  <input
                    ref={inputRef}
                    type="text"
                    value={newFileName}
                    onChange={(event) => setNewFileName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') {
                        event.preventDefault();
                        handleCloseCreate();
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="e.g. notes.txt"
                    disabled={creating}
                  />
                </div>
                {createError && (
                  <div className="text-sm text-red-600 dark:text-red-400">
                    {createError}
                  </div>
                )}
                <div className="flex justify-end gap-3 mt-6">
                  <button
                    type="button"
                    onClick={handleCloseCreate}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
                    disabled={creating}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed"
                    disabled={creating}
                  >
                    {creating ? 'Creating...' : 'Create'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
