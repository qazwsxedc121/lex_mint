/**
 * FileTree - Recursive file tree component
 */

import React, { Fragment, useEffect, useRef, useState } from 'react';
import { Menu, Transition } from '@headlessui/react';
import { FolderIcon, FolderOpenIcon, DocumentIcon, ChevronRightIcon, ChevronDownIcon, EllipsisVerticalIcon, TrashIcon, Square2StackIcon } from '@heroicons/react/24/outline';
import type { FileNode } from '../../../types/project';

type FileTreeMenuAction = 'new-file' | 'new-folder' | 'delete-folder' | 'duplicate-file' | 'delete-file';
type FileTreeCreateKind = 'file' | 'folder';

interface FileTreeProps {
  tree: FileNode;
  selectedPath: string | null;
  onFileSelect: (path: string) => void;
  onCreateFile?: (directoryPath: string, filename: string) => Promise<string>;
  onCreateFolder?: (directoryPath: string, folderName: string) => Promise<string>;
  onDuplicateFile?: (filePath: string, newFileName: string) => Promise<string>;
  onDeleteFile?: (filePath: string) => Promise<void>;
  onDeleteFolder?: (directoryPath: string) => Promise<void>;
  level?: number;
}

interface FileTreeItemProps {
  tree: FileNode;
  selectedPath: string | null;
  onFileSelect: (path: string) => void;
  level: number;
  onMenuAction?: (action: FileTreeMenuAction, directoryPath: string, directoryName: string) => void;
  allowCreateFile: boolean;
  allowCreateFolder: boolean;
  allowDuplicateFile: boolean;
  allowDeleteFile: boolean;
  allowDeleteFolder: boolean;
}

const FileTreeItem: React.FC<FileTreeItemProps> = ({
  tree,
  selectedPath,
  onFileSelect,
  level,
  onMenuAction,
  allowCreateFile,
  allowCreateFolder,
  allowDuplicateFile,
  allowDeleteFile,
  allowDeleteFolder,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const isDirectory = tree.type === 'directory';
  const isSelected = selectedPath === tree.path;
  const showMenu = isDirectory
    ? (allowCreateFile || allowCreateFolder || allowDeleteFolder)
    : (allowDuplicateFile || allowDeleteFile);
  const canDeleteFolder = allowDeleteFolder && tree.path !== '';

  const handleClick = () => {
    if (isDirectory) {
      setIsExpanded(!isExpanded);
    } else {
      onFileSelect(tree.path);
    }
  };

  const handleMenuAction = (event: React.MouseEvent<HTMLButtonElement>, action: FileTreeMenuAction) => {
    event.stopPropagation();
    if ((action === 'new-file' || action === 'new-folder') && isDirectory && !isExpanded) {
      setIsExpanded(true);
    }
    onMenuAction?.(action, tree.path, tree.name);
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
        {showMenu && (
          <Menu as="div" data-name="file-tree-item-menu" className="relative ml-auto flex-shrink-0">
            <Menu.Button
              type="button"
              onClick={(event) => event.stopPropagation()}
              className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:text-gray-500 dark:hover:text-gray-300 dark:hover:bg-gray-700 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity"
              title="Actions"
            >
              <EllipsisVerticalIcon className="h-4 w-4" />
            </Menu.Button>
            <Transition
              as={Fragment}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <Menu.Items
                data-name="file-tree-item-menu-items"
                className="absolute right-0 mt-1 w-44 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-lg z-20 focus:outline-none"
              >
                <div className="py-1">
                  {isDirectory && allowCreateFile && (
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          type="button"
                          onClick={(event) => handleMenuAction(event, 'new-file')}
                          className={`flex w-full items-center px-3 py-2 text-sm ${
                            active
                              ? 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                              : 'text-gray-700 dark:text-gray-200'
                          }`}
                        >
                          <DocumentIcon className="h-4 w-4 mr-2 flex-shrink-0" />
                          New file
                        </button>
                      )}
                    </Menu.Item>
                  )}
                  {isDirectory && allowCreateFolder && (
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          type="button"
                          onClick={(event) => handleMenuAction(event, 'new-folder')}
                          className={`flex w-full items-center px-3 py-2 text-sm ${
                            active
                              ? 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                              : 'text-gray-700 dark:text-gray-200'
                          }`}
                        >
                          <FolderIcon className="h-4 w-4 mr-2 flex-shrink-0" />
                          New folder
                        </button>
                      )}
                    </Menu.Item>
                  )}
                  {isDirectory && allowDeleteFolder && (
                    <Menu.Item disabled={!canDeleteFolder}>
                      {({ active, disabled }) => (
                        <button
                          type="button"
                          disabled={disabled}
                          onClick={
                            disabled
                              ? undefined
                              : (event) => handleMenuAction(event, 'delete-folder')
                          }
                          className={`flex w-full items-center px-3 py-2 text-sm ${
                            disabled
                              ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed'
                              : active
                              ? 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                              : 'text-red-600 dark:text-red-400'
                          }`}
                        >
                          <TrashIcon className="h-4 w-4 mr-2 flex-shrink-0" />
                          Delete folder
                        </button>
                      )}
                    </Menu.Item>
                  )}
                  {!isDirectory && allowDuplicateFile && (
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          type="button"
                          onClick={(event) => handleMenuAction(event, 'duplicate-file')}
                          className={`flex w-full items-center px-3 py-2 text-sm ${
                            active
                              ? 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                              : 'text-gray-700 dark:text-gray-200'
                          }`}
                        >
                          <Square2StackIcon className="h-4 w-4 mr-2 flex-shrink-0" />
                          Duplicate file
                        </button>
                      )}
                    </Menu.Item>
                  )}
                  {!isDirectory && allowDeleteFile && (
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          type="button"
                          onClick={(event) => handleMenuAction(event, 'delete-file')}
                          className={`flex w-full items-center px-3 py-2 text-sm ${
                            active
                              ? 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                              : 'text-red-600 dark:text-red-400'
                          }`}
                        >
                          <TrashIcon className="h-4 w-4 mr-2 flex-shrink-0" />
                          Delete file
                        </button>
                      )}
                    </Menu.Item>
                  )}
                </div>
              </Menu.Items>
            </Transition>
          </Menu>
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
              onMenuAction={onMenuAction}
              allowCreateFile={allowCreateFile}
              allowCreateFolder={allowCreateFolder}
              allowDuplicateFile={allowDuplicateFile}
              allowDeleteFile={allowDeleteFile}
              allowDeleteFolder={allowDeleteFolder}
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
  onCreateFolder,
  onDuplicateFile,
  onDeleteFile,
  onDeleteFolder,
}) => {
  const [createTarget, setCreateTarget] = useState<{
    directoryPath: string;
    directoryName: string;
    kind: FileTreeCreateKind;
  } | null>(null);
  const [newEntryName, setNewEntryName] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ directoryPath: string; directoryName: string } | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [duplicateTarget, setDuplicateTarget] = useState<{ filePath: string; fileName: string } | null>(null);
  const [duplicateName, setDuplicateName] = useState('');
  const [duplicateError, setDuplicateError] = useState<string | null>(null);
  const [duplicating, setDuplicating] = useState(false);
  const [deleteFileTarget, setDeleteFileTarget] = useState<{ filePath: string; fileName: string } | null>(null);
  const [deleteFileConfirm, setDeleteFileConfirm] = useState('');
  const [deleteFileError, setDeleteFileError] = useState<string | null>(null);
  const [deletingFile, setDeletingFile] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const deleteInputRef = useRef<HTMLInputElement | null>(null);
  const duplicateInputRef = useRef<HTMLInputElement | null>(null);
  const deleteFileInputRef = useRef<HTMLInputElement | null>(null);
  const allowCreateFile = Boolean(onCreateFile);
  const allowCreateFolder = Boolean(onCreateFolder);
  const allowDuplicateFile = Boolean(onDuplicateFile);
  const allowDeleteFile = Boolean(onDeleteFile);
  const allowDeleteFolder = Boolean(onDeleteFolder);

  useEffect(() => {
    if (!createTarget) return undefined;
    const timer = window.setTimeout(() => {
      inputRef.current?.focus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [createTarget]);

  useEffect(() => {
    if (!deleteTarget) return undefined;
    const timer = window.setTimeout(() => {
      deleteInputRef.current?.focus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [deleteTarget]);

  useEffect(() => {
    if (!duplicateTarget) return undefined;
    const timer = window.setTimeout(() => {
      duplicateInputRef.current?.focus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [duplicateTarget]);

  useEffect(() => {
    if (!deleteFileTarget) return undefined;
    const timer = window.setTimeout(() => {
      deleteFileInputRef.current?.focus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [deleteFileTarget]);

  const getDuplicateName = (filename: string, siblingNames: Set<string>) => {
    const dotIndex = filename.lastIndexOf('.');
    const baseName = dotIndex > 0 ? filename.slice(0, dotIndex) : filename;
    const ext = dotIndex > 0 ? filename.slice(dotIndex) : '';
    const normalizedBase = baseName.replace(/-copy(?:-\d+)?$/, '');
    const copyBase = `${normalizedBase}-copy`;
    let candidate = `${copyBase}${ext}`;
    if (!siblingNames.has(candidate)) {
      return candidate;
    }
    let index = 2;
    while (siblingNames.has(candidate)) {
      candidate = `${copyBase}-${index}${ext}`;
      index += 1;
    }
    return candidate;
  };

  const splitPath = (pathValue: string) => {
    const normalized = pathValue.replace(/\\/g, '/');
    const lastSlash = normalized.lastIndexOf('/');
    if (lastSlash === -1) {
      return { directory: '', name: normalized };
    }
    return {
      directory: normalized.slice(0, lastSlash),
      name: normalized.slice(lastSlash + 1),
    };
  };

  const findNodeByPath = (node: FileNode, pathValue: string): FileNode | null => {
    if (node.path === pathValue) {
      return node;
    }
    if (!node.children) {
      return null;
    }
    for (const child of node.children) {
      const match = findNodeByPath(child, pathValue);
      if (match) {
        return match;
      }
    }
    return null;
  };

  const getSiblingNames = (directoryPath: string) => {
    const targetNode = findNodeByPath(tree, directoryPath);
    if (!targetNode || !targetNode.children) {
      return new Set<string>();
    }
    return new Set(targetNode.children.map((child) => child.name));
  };

  const handleMenuAction = (action: FileTreeMenuAction, directoryPath: string, directoryName: string) => {
    if (action === 'new-file') {
      setCreateTarget({ directoryPath, directoryName, kind: 'file' });
      setNewEntryName('');
      setCreateError(null);
      return;
    }
    if (action === 'new-folder') {
      setCreateTarget({ directoryPath, directoryName, kind: 'folder' });
      setNewEntryName('');
      setCreateError(null);
      return;
    }
    if (action === 'delete-folder') {
      setDeleteTarget({ directoryPath, directoryName });
      setDeleteConfirm('');
      setDeleteError(null);
    }
    if (action === 'duplicate-file') {
      const { directory, name } = splitPath(directoryPath);
      const siblingNames = getSiblingNames(directory);
      setDuplicateTarget({ filePath: directoryPath, fileName: name });
      setDuplicateName(getDuplicateName(name, siblingNames));
      setDuplicateError(null);
    }
    if (action === 'delete-file') {
      const { name } = splitPath(directoryPath);
      setDeleteFileTarget({ filePath: directoryPath, fileName: name });
      setDeleteFileConfirm('');
      setDeleteFileError(null);
    }
  };

  const handleCloseCreate = () => {
    setCreateTarget(null);
    setNewEntryName('');
    setCreateError(null);
    setCreating(false);
  };

  const handleCloseDelete = () => {
    setDeleteTarget(null);
    setDeleteConfirm('');
    setDeleteError(null);
    setDeleting(false);
  };

  const handleCloseDuplicate = () => {
    setDuplicateTarget(null);
    setDuplicateName('');
    setDuplicateError(null);
    setDuplicating(false);
  };

  const handleCloseDeleteFile = () => {
    setDeleteFileTarget(null);
    setDeleteFileConfirm('');
    setDeleteFileError(null);
    setDeletingFile(false);
  };

  const handleCreateSubmit = async () => {
    if (!createTarget || creating) return;
    const trimmedName = newEntryName.trim();
    const label = createTarget.kind === 'folder' ? 'folder' : 'file';
    if (!trimmedName) {
      setCreateError(`Please enter a ${label} name.`);
      return;
    }
    if (/[\\/]/.test(trimmedName)) {
      setCreateError(`${label.charAt(0).toUpperCase() + label.slice(1)} name cannot contain / or \\\\.`);
      return;
    }

    if (createTarget.kind === 'file' && !onCreateFile) {
      setCreateError('File creation is unavailable.');
      return;
    }
    if (createTarget.kind === 'folder' && !onCreateFolder) {
      setCreateError('Folder creation is unavailable.');
      return;
    }

    setCreating(true);
    setCreateError(null);
    try {
      if (createTarget.kind === 'file') {
        const createdPath = await onCreateFile(createTarget.directoryPath, trimmedName);
        handleCloseCreate();
        onFileSelect(createdPath);
      } else {
        await onCreateFolder(createTarget.directoryPath, trimmedName);
        handleCloseCreate();
      }
    } catch (err: any) {
      const fallbackMessage = createTarget.kind === 'folder' ? 'Failed to create folder.' : 'Failed to create file.';
      const message = err?.response?.data?.detail || err?.message || fallbackMessage;
      setCreateError(message);
      setCreating(false);
    }
  };

  const handleDeleteSubmit = async () => {
    if (!deleteTarget || deleting || !onDeleteFolder) return;
    if (deleteConfirm.trim() !== deleteTarget.directoryPath) {
      setDeleteError('Please type the folder path to confirm.');
      return;
    }

    setDeleting(true);
    setDeleteError(null);
    try {
      await onDeleteFolder(deleteTarget.directoryPath);
      handleCloseDelete();
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to delete folder.';
      setDeleteError(message);
      setDeleting(false);
    }
  };

  const handleDuplicateSubmit = async () => {
    if (!duplicateTarget || duplicating || !onDuplicateFile) return;
    const trimmedName = duplicateName.trim();
    if (!trimmedName) {
      setDuplicateError('Please enter a file name.');
      return;
    }
    if (/[\\/]/.test(trimmedName)) {
      setDuplicateError('File name cannot contain / or \\\\.');
      return;
    }
    if (trimmedName === duplicateTarget.fileName) {
      setDuplicateError('Please choose a different name.');
      return;
    }

    setDuplicating(true);
    setDuplicateError(null);
    try {
      const createdPath = await onDuplicateFile(duplicateTarget.filePath, trimmedName);
      handleCloseDuplicate();
      onFileSelect(createdPath);
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to duplicate file.';
      setDuplicateError(message);
      setDuplicating(false);
    }
  };

  const handleDeleteFileSubmit = async () => {
    if (!deleteFileTarget || deletingFile || !onDeleteFile) return;
    if (deleteFileConfirm.trim() !== deleteFileTarget.fileName) {
      setDeleteFileError('Please type the file name to confirm.');
      return;
    }

    setDeletingFile(true);
    setDeleteFileError(null);
    try {
      await onDeleteFile(deleteFileTarget.filePath);
      handleCloseDeleteFile();
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to delete file.';
      setDeleteFileError(message);
      setDeletingFile(false);
    }
  };

  return (
    <div data-name="file-tree" className="h-full overflow-y-auto bg-white dark:bg-gray-800 border-r border-gray-300 dark:border-gray-700">
      <FileTreeItem
        tree={tree}
        selectedPath={selectedPath}
        onFileSelect={onFileSelect}
        level={0}
        onMenuAction={handleMenuAction}
        allowCreateFile={allowCreateFile}
        allowCreateFolder={allowCreateFolder}
        allowDuplicateFile={allowDuplicateFile}
        allowDeleteFile={allowDeleteFile}
        allowDeleteFolder={allowDeleteFolder}
      />
      {createTarget && (
        <div data-name="file-entry-create-modal" className="fixed inset-0 z-50 overflow-y-auto">
          <div
            className="fixed inset-0 bg-black bg-opacity-50"
            onClick={handleCloseCreate}
          />
          <div className="flex min-h-full items-center justify-center p-4">
            <div data-name="file-entry-create-modal-card" className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-1">
                {createTarget.kind === 'folder' ? 'New Folder' : 'New File'}
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
                    {createTarget.kind === 'folder' ? 'Folder Name' : 'File Name'}
                  </label>
                  <input
                    ref={inputRef}
                    type="text"
                    value={newEntryName}
                    onChange={(event) => setNewEntryName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') {
                        event.preventDefault();
                        handleCloseCreate();
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder={createTarget.kind === 'folder' ? 'e.g. docs' : 'e.g. notes.txt'}
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
      {duplicateTarget && (
        <div data-name="file-duplicate-modal" className="fixed inset-0 z-50 overflow-y-auto">
          <div
            className="fixed inset-0 bg-black bg-opacity-50"
            onClick={handleCloseDuplicate}
          />
          <div className="flex min-h-full items-center justify-center p-4">
            <div data-name="file-duplicate-modal-card" className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-1">
                Duplicate File
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
                Duplicate <span className="font-medium text-gray-800 dark:text-gray-200">{duplicateTarget.fileName}</span>
              </p>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  handleDuplicateSubmit();
                }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    New File Name
                  </label>
                  <input
                    ref={duplicateInputRef}
                    type="text"
                    value={duplicateName}
                    onChange={(event) => setDuplicateName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') {
                        event.preventDefault();
                        handleCloseDuplicate();
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    disabled={duplicating}
                  />
                </div>
                {duplicateError && (
                  <div className="text-sm text-red-600 dark:text-red-400">
                    {duplicateError}
                  </div>
                )}
                <div className="flex justify-end gap-3 mt-6">
                  <button
                    type="button"
                    onClick={handleCloseDuplicate}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
                    disabled={duplicating}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed"
                    disabled={duplicating}
                  >
                    {duplicating ? 'Duplicating...' : 'Duplicate'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
      {deleteTarget && (
        <div data-name="folder-delete-modal" className="fixed inset-0 z-50 overflow-y-auto">
          <div
            className="fixed inset-0 bg-black bg-opacity-50"
            onClick={handleCloseDelete}
          />
          <div className="flex min-h-full items-center justify-center p-4">
            <div data-name="folder-delete-modal-card" className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-1">
                Delete Folder
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
                This will permanently delete <span className="font-medium text-gray-800 dark:text-gray-200">{deleteTarget.directoryPath}</span> and all contents.
              </p>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  handleDeleteSubmit();
                }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Type the folder path to confirm
                  </label>
                  <input
                    ref={deleteInputRef}
                    type="text"
                    value={deleteConfirm}
                    onChange={(event) => setDeleteConfirm(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') {
                        event.preventDefault();
                        handleCloseDelete();
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-red-500 focus:border-red-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder={deleteTarget.directoryPath}
                    disabled={deleting}
                  />
                </div>
                {deleteError && (
                  <div className="text-sm text-red-600 dark:text-red-400">
                    {deleteError}
                  </div>
                )}
                <div className="flex justify-end gap-3 mt-6">
                  <button
                    type="button"
                    onClick={handleCloseDelete}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
                    disabled={deleting}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-60 disabled:cursor-not-allowed"
                    disabled={deleting || deleteConfirm.trim() !== deleteTarget.directoryPath}
                  >
                    {deleting ? 'Deleting...' : 'Delete'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
      {deleteFileTarget && (
        <div data-name="file-delete-modal" className="fixed inset-0 z-50 overflow-y-auto">
          <div
            className="fixed inset-0 bg-black bg-opacity-50"
            onClick={handleCloseDeleteFile}
          />
          <div className="flex min-h-full items-center justify-center p-4">
            <div data-name="file-delete-modal-card" className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-1">
                Delete File
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
                This will permanently delete <span className="font-medium text-gray-800 dark:text-gray-200">{deleteFileTarget.fileName}</span>.
              </p>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  handleDeleteFileSubmit();
                }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Type the file name to confirm
                  </label>
                  <input
                    ref={deleteFileInputRef}
                    type="text"
                    value={deleteFileConfirm}
                    onChange={(event) => setDeleteFileConfirm(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') {
                        event.preventDefault();
                        handleCloseDeleteFile();
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-red-500 focus:border-red-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder={deleteFileTarget.fileName}
                    disabled={deletingFile}
                  />
                </div>
                {deleteFileError && (
                  <div className="text-sm text-red-600 dark:text-red-400">
                    {deleteFileError}
                  </div>
                )}
                <div className="flex justify-end gap-3 mt-6">
                  <button
                    type="button"
                    onClick={handleCloseDeleteFile}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
                    disabled={deletingFile}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-60 disabled:cursor-not-allowed"
                    disabled={deletingFile || deleteFileConfirm.trim() !== deleteFileTarget.fileName}
                  >
                    {deletingFile ? 'Deleting...' : 'Delete'}
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
