/**
 * FileViewer - File content viewer with syntax highlighting
 */

import React, { useEffect, useRef } from 'react';
import Prism from 'prismjs';
import 'prismjs/themes/prism-tomorrow.css';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-jsx';
import 'prismjs/components/prism-tsx';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-yaml';
import 'prismjs/components/prism-markdown';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-css';
import type { FileContent } from '../../../types/project';
import { Breadcrumb } from './Breadcrumb';

interface FileViewerProps {
  projectName: string;
  content: FileContent | null;
  loading: boolean;
  error: string | null;
}

const getLanguageFromPath = (path: string, _mimeType: string): string => {
  const ext = path.split('.').pop()?.toLowerCase() || '';

  const languageMap: Record<string, string> = {
    'py': 'python',
    'ts': 'typescript',
    'tsx': 'tsx',
    'js': 'javascript',
    'jsx': 'jsx',
    'json': 'json',
    'yaml': 'yaml',
    'yml': 'yaml',
    'md': 'markdown',
    'sh': 'bash',
    'bash': 'bash',
    'css': 'css',
    'html': 'html',
    'xml': 'xml',
    'sql': 'sql',
  };

  return languageMap[ext] || 'text';
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const FileViewer: React.FC<FileViewerProps> = ({ projectName, content, loading, error }) => {
  const codeRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (codeRef.current && content) {
      Prism.highlightElement(codeRef.current);
    }
  }, [content]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-red-600 dark:text-red-400">{error}</div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-white dark:bg-gray-900">
        <p className="text-gray-500 dark:text-gray-400 mb-2">Select a file to view</p>
      </div>
    );
  }

  const language = getLanguageFromPath(content.path, content.mime_type);

  return (
    <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 overflow-hidden">
      {/* Header */}
      <div className="border-b border-gray-300 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800">
        <Breadcrumb projectName={projectName} filePath={content.path} />
        <div className="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400">
          <span>{formatFileSize(content.size)}</span>
          <span>{content.encoding}</span>
          <span>{content.mime_type}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <pre className="!m-0 !bg-transparent">
          <code
            ref={codeRef}
            className={`language-${language} !bg-transparent`}
            style={{ fontSize: '14px', lineHeight: '1.6' }}
          >
            {content.content}
          </code>
        </pre>
      </div>
    </div>
  );
};
