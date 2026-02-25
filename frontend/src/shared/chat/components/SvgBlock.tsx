import React, { useEffect, useState } from 'react';
import {
  ChartBarIcon,
  ClipboardDocumentCheckIcon,
  ClipboardDocumentIcon,
  CodeBracketIcon,
} from '@heroicons/react/24/outline';
import { sanitizeSvg } from '../utils/sanitizeSvg';

interface SvgBlockProps {
  value: string;
}

export const SvgBlock: React.FC<SvgBlockProps> = ({ value }) => {
  const [sanitizedSvg, setSanitizedSvg] = useState('');
  const [error, setError] = useState('');
  const [showCode, setShowCode] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => {
    const { sanitized, error: sanitizeError } = sanitizeSvg(value);
    setSanitizedSvg(sanitized);
    setError(sanitizeError || '');
  }, [value]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (copyError) {
      console.error('Failed to copy SVG source:', copyError);
    }
  };

  const showingCode = showCode || !!error || !sanitizedSvg;

  return (
    <div data-name="svg-block-root" className="relative group my-4">
      <div data-name="svg-block-header" className="flex items-center justify-between bg-gray-800 text-gray-300 px-4 py-2 rounded-t-lg text-sm">
        <span className="font-mono">svg</span>
        <div className="flex items-center gap-2">
          {(sanitizedSvg || error) && (
            <button
              onClick={() => setShowCode(!showCode)}
              className="flex items-center gap-1.5 px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded transition-colors"
              title={showCode ? 'Show SVG' : 'Show code'}
            >
              {showingCode ? (
                <>
                  <ChartBarIcon className="w-4 h-4" />
                  <span>SVG</span>
                </>
              ) : (
                <>
                  <CodeBracketIcon className="w-4 h-4" />
                  <span>Code</span>
                </>
              )}
            </button>
          )}
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded transition-colors"
            title={isCopied ? 'Copied' : 'Copy code'}
          >
            {isCopied ? (
              <>
                <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-400" />
                <span className="text-green-400">Copied</span>
              </>
            ) : (
              <>
                <ClipboardDocumentIcon className="w-4 h-4" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {showingCode ? (
        <div className="bg-gray-900 rounded-b-lg overflow-x-auto">
          {error && (
            <div className="px-4 py-2 text-xs text-red-400 bg-red-900/30 border-b border-red-800/50">
              Render error: {error}
            </div>
          )}
          <pre className="p-4 text-sm text-gray-200 overflow-x-auto">
            <code>{value}</code>
          </pre>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 rounded-b-lg p-4 overflow-x-auto flex justify-center [&_svg]:max-w-full [&_svg]:h-auto">
          <div dangerouslySetInnerHTML={{ __html: sanitizedSvg }} />
        </div>
      )}
    </div>
  );
};
