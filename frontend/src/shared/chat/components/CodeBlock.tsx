/**
 * CodeBlock component - renders code with syntax highlighting and copy button.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  ClipboardDocumentIcon,
  ClipboardDocumentCheckIcon,
  PlayIcon,
} from '@heroicons/react/24/outline';
import { javascriptService } from '../services/javascriptService';
import { pyodideService } from '../services/pyodideService';
import {
  getCodeExecutionSettings,
  subscribeCodeExecutionSettings,
} from '../config/codeExecution';

interface CodeBlockProps {
  language: string;
  value: string;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({ language, value }) => {
  const [runnerSettings, setRunnerSettings] = useState(() => getCodeExecutionSettings());
  const [isCopied, setIsCopied] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [runStdout, setRunStdout] = useState('');
  const [runStderr, setRunStderr] = useState('');
  const [runValue, setRunValue] = useState('');

  useEffect(() => (
    subscribeCodeExecutionSettings(() => {
      setRunnerSettings(getCodeExecutionSettings());
    })
  ), []);

  const executableLanguage = useMemo(() => {
    const normalized = (language || '').trim().toLowerCase();
    const isPython = normalized === 'python' || normalized === 'py';
    const isJavaScript = normalized === 'javascript' || normalized === 'js';
    const underCodeSizeLimit = value.length <= runnerSettings.maxCodeChars;
    return (
      underCodeSizeLimit
      && (
        (runnerSettings.enablePythonRunner && isPython)
        || (runnerSettings.enableJavaScriptRunner && isJavaScript)
      )
    );
  }, [
    language,
    runnerSettings.enableJavaScriptRunner,
    runnerSettings.enablePythonRunner,
    runnerSettings.maxCodeChars,
    value.length,
  ]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  const handleRun = async () => {
    if (!executableLanguage || isRunning) {
      return;
    }

    setIsRunning(true);
    setRunStdout('');
    setRunStderr('');
    setRunValue('');
    try {
      const normalized = (language || '').trim().toLowerCase();
      const isJavaScript = normalized === 'javascript' || normalized === 'js';
      const result = isJavaScript
        ? await javascriptService.runJavaScript(value, runnerSettings.executionTimeoutMs)
        : await pyodideService.runPython(value, runnerSettings.executionTimeoutMs);
      setRunStdout(result.stdout);
      setRunStderr(result.stderr);
      setRunValue(result.value);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setRunStderr(message);
    } finally {
      setIsRunning(false);
    }
  };

  const hasRunOutput = Boolean(runStdout || runStderr || runValue);

  return (
    <div data-name="code-block-root" className="relative my-4 w-full min-w-0 max-w-full group">
      {/* Language label and copy button */}
      <div data-name="code-block-header" className="flex min-w-0 items-center justify-between gap-2 bg-gray-800 text-gray-300 px-4 py-2 rounded-t-lg text-sm">
        <span className="min-w-0 truncate font-mono">{language || 'text'}</span>
        <div className="flex flex-shrink-0 items-center gap-2">
          {executableLanguage && (
            <button
              onClick={handleRun}
              disabled={isRunning}
              className="flex items-center gap-1.5 px-2 py-1 text-xs bg-indigo-700 hover:bg-indigo-600 disabled:opacity-60 disabled:cursor-not-allowed rounded transition-colors"
              title={isRunning ? 'Running code' : 'Run code in browser runtime'}
            >
              <PlayIcon className="w-4 h-4" />
              <span>{isRunning ? 'Running' : 'Run'}</span>
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

      {/* Code content */}
      <div className="min-w-0 max-w-full overflow-x-auto">
        <SyntaxHighlighter
          language={language || 'text'}
          style={vscDarkPlus}
          customStyle={{
            margin: 0,
            maxWidth: '100%',
            borderTopLeftRadius: 0,
            borderTopRightRadius: 0,
            borderBottomLeftRadius: '0.5rem',
            borderBottomRightRadius: '0.5rem',
          }}
          showLineNumbers
          wrapLongLines
        >
          {value}
        </SyntaxHighlighter>
      </div>

      {hasRunOutput && (
        <div data-name="code-block-execution-output" className="rounded-b-lg border border-t-0 border-gray-700 bg-gray-950 px-4 py-3 space-y-3">
          {runStdout && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-emerald-400 mb-1">stdout</div>
              <pre className="whitespace-pre-wrap break-words text-xs text-emerald-200">{runStdout}</pre>
            </div>
          )}
          {runValue && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-blue-400 mb-1">result</div>
              <pre className="whitespace-pre-wrap break-words text-xs text-blue-200">{runValue}</pre>
            </div>
          )}
          {runStderr && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-rose-400 mb-1">stderr</div>
              <pre className="whitespace-pre-wrap break-words text-xs text-rose-200">{runStderr}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
