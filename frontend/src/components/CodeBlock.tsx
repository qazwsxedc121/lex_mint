/**
 * CodeBlock component - renders code with syntax highlighting and copy button.
 */

import React, { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ClipboardDocumentIcon, ClipboardDocumentCheckIcon } from '@heroicons/react/24/outline';

interface CodeBlockProps {
  language: string;
  value: string;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({ language, value }) => {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  return (
    <div className="relative group my-4">
      {/* 语言标签和复制按钮 */}
      <div className="flex items-center justify-between bg-gray-800 text-gray-300 px-4 py-2 rounded-t-lg text-sm">
        <span className="font-mono">{language || 'text'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded transition-colors"
          title={isCopied ? '已复制' : '复制代码'}
        >
          {isCopied ? (
            <>
              <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-400" />
              <span className="text-green-400">已复制</span>
            </>
          ) : (
            <>
              <ClipboardDocumentIcon className="w-4 h-4" />
              <span>复制</span>
            </>
          )}
        </button>
      </div>

      {/* 代码内容 */}
      <SyntaxHighlighter
        language={language || 'text'}
        style={vscDarkPlus}
        customStyle={{
          margin: 0,
          borderTopLeftRadius: 0,
          borderTopRightRadius: 0,
          borderBottomLeftRadius: '0.5rem',
          borderBottomRightRadius: '0.5rem',
        }}
        showLineNumbers
      >
        {value}
      </SyntaxHighlighter>
    </div>
  );
};
