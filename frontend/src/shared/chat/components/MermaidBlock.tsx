/**
 * MermaidBlock component - renders mermaid diagram code as SVG with a toggle to view raw source.
 * Debounces rendering to handle streaming (value changing on every token).
 */

import React, { useState, useEffect, useId, useRef, useCallback } from 'react';
import mermaid from 'mermaid';
import { ClipboardDocumentIcon, ClipboardDocumentCheckIcon, CodeBracketIcon, ChartBarIcon } from '@heroicons/react/24/outline';

interface MermaidBlockProps {
  value: string;
}

function isDarkMode(): boolean {
  return document.documentElement.classList.contains('dark');
}

/**
 * Fix common LLM mistakes in mermaid syntax before rendering:
 * - Single `%` used for comments instead of `%%`
 * - Strip lines that are purely comments (to avoid parse errors from non-ASCII content)
 */
function preprocessMermaid(source: string): string {
  return source
    .split('\n')
    .map((line) => {
      // Replace lone % (not part of %%) with %% for inline comments
      // Uses lookbehind/lookahead to only match isolated %
      return line.replace(/(?<!%)%(?!%)/g, '%%');
    })
    .join('\n');
}

export const MermaidBlock: React.FC<MermaidBlockProps> = ({ value }) => {
  const instanceId = useId();
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [showCode, setShowCode] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track the latest value to avoid stale renders after debounce
  const latestValueRef = useRef(value);

  useEffect(() => {
    latestValueRef.current = value;
  }, [value]);

  // Stable mermaid ID derived from useId (strip colons for valid HTML id)
  const mermaidId = `mermaid-${instanceId.replace(/:/g, '')}`;

  const renderDiagram = useCallback(async (source: string) => {
    try {
      // Re-initialize mermaid to pick up current theme
      mermaid.initialize({
        startOnLoad: false,
        theme: isDarkMode() ? 'dark' : 'default',
        securityLevel: 'loose',
      });

      const { svg: renderedSvg } = await mermaid.render(mermaidId, preprocessMermaid(source.trim()));
      // Only apply if source is still current (avoids flash from stale render)
      if (latestValueRef.current === source) {
        setSvg(renderedSvg);
        setError('');
      }
    } catch (err: any) {
      console.error('Mermaid render error:', err);
      if (latestValueRef.current === source) {
        setError(err?.message || 'Failed to render diagram');
        setSvg('');
      }
      // Clean up any leftover error element mermaid may have inserted
      const errorEl = document.getElementById(`d${mermaidId}`);
      if (errorEl) errorEl.remove();
    }
  }, [mermaidId]);

  // Debounced render: wait 500ms after last value change before attempting render.
  // This prevents constant parse errors while the LLM is streaming tokens.
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => {
      renderDiagram(value);
    }, 500);
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [value, renderDiagram]);

  // Watch for dark mode changes via MutationObserver on <html> class
  useEffect(() => {
    const observer = new MutationObserver(() => {
      renderDiagram(latestValueRef.current);
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    });
    return () => observer.disconnect();
  }, [renderDiagram]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy mermaid source:', err);
    }
  };

  // While we have no SVG yet and no error, show the raw code as a loading state
  const showingCode = showCode || (!svg && !error);

  return (
    <div data-name="mermaid-block-root" className="relative group my-4">
      {/* Header */}
      <div data-name="mermaid-block-header" className="flex items-center justify-between bg-gray-800 text-gray-300 px-4 py-2 rounded-t-lg text-sm">
        <span className="font-mono">mermaid</span>
        <div className="flex items-center gap-2">
          {/* Toggle button — only show when we have a rendered diagram to switch to */}
          {(svg || error) && (
            <button
              onClick={() => setShowCode(!showCode)}
              className="flex items-center gap-1.5 px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded transition-colors"
              title={showCode ? 'Show diagram' : 'Show code'}
            >
              {showCode || error ? (
                <>
                  <ChartBarIcon className="w-4 h-4" />
                  <span>Diagram</span>
                </>
              ) : (
                <>
                  <CodeBracketIcon className="w-4 h-4" />
                  <span>Code</span>
                </>
              )}
            </button>
          )}
          {/* Copy button */}
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

      {/* Content */}
      {showingCode || error ? (
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
        <div
          ref={containerRef}
          className="bg-white dark:bg-gray-900 rounded-b-lg p-4 overflow-x-auto flex justify-center"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      )}
    </div>
  );
};
