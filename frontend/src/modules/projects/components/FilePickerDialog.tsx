import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ChevronDownIcon,
  ChevronRightIcon,
  DocumentIcon,
  FolderIcon,
  FolderOpenIcon,
} from '@heroicons/react/24/outline';
import type { FileNode } from '../../../types/project';
import { useFileTree } from '../hooks/useFileTree';

interface FilePickerDialogProps {
  projectId: string;
  isOpen: boolean;
  title: string;
  selectedPath?: string | null;
  onClose: () => void;
  onSelect: (filePath: string) => void;
}

interface FileTreeSelectNodeProps {
  node: FileNode;
  level: number;
  activePath: string | null;
  forceExpand: boolean;
  expandedDirs: Set<string>;
  onToggleDirectory: (path: string) => void;
  onSelectFile: (path: string) => void;
}

const normalizePath = (pathValue: string): string => pathValue.replace(/\\/g, '/');

const pathContainsQuery = (node: FileNode, normalizedQuery: string): boolean => {
  if (!normalizedQuery) {
    return true;
  }
  const nodeName = normalizePath(node.name).toLowerCase();
  const nodePath = normalizePath(node.path).toLowerCase();
  return nodeName.includes(normalizedQuery) || nodePath.includes(normalizedQuery);
};

const filterTreeByQuery = (node: FileNode, normalizedQuery: string): FileNode | null => {
  if (!normalizedQuery) {
    return node;
  }
  if (node.type === 'file') {
    return pathContainsQuery(node, normalizedQuery) ? node : null;
  }
  const filteredChildren = (node.children || [])
    .map((child) => filterTreeByQuery(child, normalizedQuery))
    .filter((child): child is FileNode => Boolean(child));
  if (pathContainsQuery(node, normalizedQuery) || filteredChildren.length > 0) {
    return {
      ...node,
      children: filteredChildren,
    };
  }
  return null;
};

const collectExpandedPathsForFile = (filePath: string | null): Set<string> => {
  const expanded = new Set<string>(['']);
  if (!filePath) {
    return expanded;
  }

  const normalizedFilePath = normalizePath(filePath);
  const pathParts = normalizedFilePath.split('/').filter(Boolean);
  if (pathParts.length <= 1) {
    return expanded;
  }

  let current = '';
  for (let index = 0; index < pathParts.length - 1; index += 1) {
    current = current ? `${current}/${pathParts[index]}` : pathParts[index];
    expanded.add(current);
  }
  return expanded;
};

const FileTreeSelectNode: React.FC<FileTreeSelectNodeProps> = ({
  node,
  level,
  activePath,
  forceExpand,
  expandedDirs,
  onToggleDirectory,
  onSelectFile,
}) => {
  const isDirectory = node.type === 'directory';
  const isExpanded = isDirectory && (forceExpand || expandedDirs.has(node.path));
  const isSelected = node.type === 'file' && activePath === node.path;

  if (isDirectory) {
    return (
      <div data-name={`file-picker-directory-${node.path || 'root'}`}>
        <button
          type="button"
          onClick={() => onToggleDirectory(node.path)}
          className="w-full flex items-center gap-1 px-2 py-1 text-left hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
        >
          {isExpanded ? (
            <ChevronDownIcon className="h-4 w-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
          ) : (
            <ChevronRightIcon className="h-4 w-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
          )}
          {isExpanded ? (
            <FolderOpenIcon className="h-4 w-4 text-blue-500 dark:text-blue-400 flex-shrink-0" />
          ) : (
            <FolderIcon className="h-4 w-4 text-blue-500 dark:text-blue-400 flex-shrink-0" />
          )}
          <span className="text-sm text-gray-800 dark:text-gray-100 truncate">{node.name || '/'}</span>
        </button>
        {isExpanded && (node.children || []).length > 0 && (
          <div className={level >= 0 ? 'ml-4' : ''}>
            {(node.children || []).map((child) => (
              <FileTreeSelectNode
                key={`${child.type}:${child.path || child.name}`}
                node={child}
                level={level + 1}
                activePath={activePath}
                forceExpand={forceExpand}
                expandedDirs={expandedDirs}
                onToggleDirectory={onToggleDirectory}
                onSelectFile={onSelectFile}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => onSelectFile(node.path)}
      data-name={`file-picker-file-${node.path}`}
      className={`w-full flex items-center gap-2 px-2 py-1 text-left rounded ${
        isSelected
          ? 'bg-blue-100 dark:bg-blue-900/40'
          : 'hover:bg-gray-100 dark:hover:bg-gray-700'
      }`}
    >
      <DocumentIcon className="h-4 w-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
      <span className="text-sm text-gray-800 dark:text-gray-100 truncate">{node.name}</span>
      <span className="text-[11px] text-gray-500 dark:text-gray-400 truncate ml-auto">{node.path}</span>
    </button>
  );
};

export const FilePickerDialog: React.FC<FilePickerDialogProps> = ({
  projectId,
  isOpen,
  title,
  selectedPath = null,
  onClose,
  onSelect,
}) => {
  const { t } = useTranslation('projects');
  const [query, setQuery] = useState('');
  const [pendingPath, setPendingPath] = useState<string | null>(selectedPath);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(() => collectExpandedPathsForFile(selectedPath));
  const { tree, loading, error } = useFileTree(isOpen ? projectId : null);

  useEffect(() => {
    if (!isOpen) {
      setQuery('');
      return;
    }
    setPendingPath(selectedPath);
    setExpandedDirs(collectExpandedPathsForFile(selectedPath));
  }, [isOpen, selectedPath]);

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const normalizedQuery = query.trim().toLowerCase();
  const filteredTree = useMemo(() => {
    if (!tree) {
      return null;
    }
    return filterTreeByQuery(tree, normalizedQuery);
  }, [tree, normalizedQuery]);

  const visibleNodes = useMemo(() => {
    if (!filteredTree) {
      return [] as FileNode[];
    }
    if (filteredTree.type === 'directory' && filteredTree.path === '') {
      return filteredTree.children || [];
    }
    return [filteredTree];
  }, [filteredTree]);

  const hasNoFiles = !loading && !error && visibleNodes.length === 0;
  const forceExpand = normalizedQuery.length > 0;

  const handleToggleDirectory = (path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const handleConfirm = () => {
    if (!pendingPath) {
      return;
    }
    onSelect(pendingPath);
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div data-name="file-picker-dialog" className="fixed inset-0 z-50 p-4 sm:p-6 lg:p-8">
      <button
        type="button"
        aria-label={t('common:close')}
        onClick={onClose}
        className="absolute inset-0 bg-black/40"
      />
      <div className="relative mx-auto w-full max-w-5xl h-full max-h-[80vh] bg-white dark:bg-gray-900 rounded-lg border border-gray-300 dark:border-gray-700 shadow-2xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
          <div className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">
            {title}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            {t('common:close')}
          </button>
        </div>

        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <input
            data-name="file-picker-dialog-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('projectWorkflow.fileSearchPlaceholder')}
            className="w-full text-sm px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
          />
        </div>

        <div className="flex-1 min-h-0 overflow-auto px-3 py-2">
          {loading && (
            <div className="px-2 py-2 text-sm text-gray-500 dark:text-gray-400">
              {t('projectWorkflow.fileSearchLoading')}
            </div>
          )}
          {error && (
            <div className="px-2 py-2 text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          )}
          {hasNoFiles && (
            <div className="px-2 py-2 text-sm text-gray-500 dark:text-gray-400">
              {t('projectWorkflow.fileSearchNoResults')}
            </div>
          )}
          {!loading && !error && visibleNodes.map((node) => (
            <FileTreeSelectNode
              key={`${node.type}:${node.path || node.name}`}
              node={node}
              level={0}
              activePath={pendingPath}
              forceExpand={forceExpand}
              expandedDirs={expandedDirs}
              onToggleDirectory={handleToggleDirectory}
              onSelectFile={setPendingPath}
            />
          ))}
        </div>

        <div className="border-t border-gray-200 dark:border-gray-700 px-4 py-2 space-y-2">
          <div className="text-xs text-gray-600 dark:text-gray-400 truncate">
            {pendingPath || t('common:select')}
          </div>
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-xs rounded border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              {t('common:cancel')}
            </button>
            <button
              type="button"
              disabled={!pendingPath}
              onClick={handleConfirm}
              className="px-3 py-1.5 text-xs rounded bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed"
            >
              {t('common:confirm')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
