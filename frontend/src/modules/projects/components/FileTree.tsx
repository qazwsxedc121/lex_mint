/**
 * FileTree - Recursive file tree component
 */

import React, { useState } from 'react';
import { FolderIcon, FolderOpenIcon, DocumentIcon, ChevronRightIcon, ChevronDownIcon } from '@heroicons/react/24/outline';
import type { FileNode } from '../../../types/project';

interface FileTreeProps {
  tree: FileNode;
  selectedPath: string | null;
  onFileSelect: (path: string) => void;
  level?: number;
}

const FileTreeItem: React.FC<FileTreeProps> = ({ tree, selectedPath, onFileSelect, level = 0 }) => {
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

  return (
    <div>
      <div
        className={`flex items-center py-1 px-2 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors ${
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
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const FileTree: React.FC<Omit<FileTreeProps, 'level'>> = ({ tree, selectedPath, onFileSelect }) => {
  return (
    <div className="h-full overflow-y-auto bg-white dark:bg-gray-800 border-r border-gray-300 dark:border-gray-700">
      <FileTreeItem tree={tree} selectedPath={selectedPath} onFileSelect={onFileSelect} level={0} />
    </div>
  );
};
