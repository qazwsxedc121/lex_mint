import React, { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PageHeader, SuccessMessage } from './components/common';
import {
  getCodeExecutionSettings,
  getDefaultCodeExecutionSettings,
  setCodeExecutionSettings,
  type CodeExecutionSettings,
} from '../../shared/chat/config/codeExecution';
import { pyodideService } from '../../shared/chat/services/pyodideService';

const toPositiveInt = (value: string, fallback: number): number => {
  const parsed = Number.parseInt(value, 10);
  if (Number.isFinite(parsed) && parsed > 0) {
    return parsed;
  }
  return fallback;
};

export const CodeExecutionSettingsPage: React.FC = () => {
  const { t } = useTranslation('settings');
  const initialSettings = useMemo(() => getCodeExecutionSettings(), []);
  const codeTemplates = useMemo(() => ([
    {
      key: 'hello',
      label: t('codeExecution.templateHello'),
      code: 'print("hello from pyodide")\n2 + 3',
    },
    {
      key: 'loop',
      label: t('codeExecution.templateLoop'),
      code: 'for i in range(3):\n    print("index:", i)\n"done"',
    },
    {
      key: 'function',
      label: t('codeExecution.templateFunction'),
      code: 'def fib(n):\n    a, b = 0, 1\n    out = []\n    for _ in range(n):\n        out.append(a)\n        a, b = b, a + b\n    return out\n\nfib(8)',
    },
    {
      key: 'exception',
      label: t('codeExecution.templateException'),
      code: 'try:\n    1 / 0\nexcept Exception as e:\n    print("caught:", e)\n"recovered"',
    },
  ]), [t]);

  const [enablePythonRunner, setEnablePythonRunner] = useState(initialSettings.enablePythonRunner);
  const [executionTimeoutMs, setExecutionTimeoutMs] = useState(String(initialSettings.executionTimeoutMs));
  const [maxCodeChars, setMaxCodeChars] = useState(String(initialSettings.maxCodeChars));
  const [saved, setSaved] = useState(false);
  const [testCode, setTestCode] = useState('print("hello")\n2 + 3');
  const [isRunningTest, setIsRunningTest] = useState(false);
  const [testStdout, setTestStdout] = useState('');
  const [testStderr, setTestStderr] = useState('');
  const [testResult, setTestResult] = useState('');
  const testCodeRef = useRef<HTMLTextAreaElement | null>(null);

  const handleSave = () => {
    const current = getCodeExecutionSettings();
    const nextSettings: CodeExecutionSettings = {
      enablePythonRunner,
      executionTimeoutMs: toPositiveInt(executionTimeoutMs, current.executionTimeoutMs),
      maxCodeChars: toPositiveInt(maxCodeChars, current.maxCodeChars),
    };
    const normalized = setCodeExecutionSettings(nextSettings);
    setExecutionTimeoutMs(String(normalized.executionTimeoutMs));
    setMaxCodeChars(String(normalized.maxCodeChars));
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2000);
  };

  const handleReset = () => {
    const defaults = getDefaultCodeExecutionSettings();
    setEnablePythonRunner(defaults.enablePythonRunner);
    setExecutionTimeoutMs(String(defaults.executionTimeoutMs));
    setMaxCodeChars(String(defaults.maxCodeChars));
    setSaved(false);
  };

  const handleRunTest = async () => {
    const timeoutMs = toPositiveInt(executionTimeoutMs, initialSettings.executionTimeoutMs);
    const codeCharLimit = toPositiveInt(maxCodeChars, initialSettings.maxCodeChars);
    if (!enablePythonRunner || isRunningTest || testCode.length > codeCharLimit) {
      return;
    }

    setIsRunningTest(true);
    setTestStdout('');
    setTestStderr('');
    setTestResult('');
    try {
      const result = await pyodideService.runPython(testCode, timeoutMs);
      setTestStdout(result.stdout);
      setTestStderr(result.stderr);
      setTestResult(result.value);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setTestStderr(message);
    } finally {
      setIsRunningTest(false);
    }
  };

  const testCodeTooLong = testCode.length > toPositiveInt(maxCodeChars, initialSettings.maxCodeChars);
  const hasTestOutput = Boolean(testStdout || testStderr || testResult);

  const handleTestCodeKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Tab') {
      return;
    }
    event.preventDefault();

    const textarea = testCodeRef.current;
    if (!textarea) {
      return;
    }

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const nextCode = `${testCode.slice(0, start)}\t${testCode.slice(end)}`;
    setTestCode(nextCode);

    window.requestAnimationFrame(() => {
      textarea.selectionStart = start + 1;
      textarea.selectionEnd = start + 1;
    });
  };

  return (
    <div className="space-y-6" data-name="code-execution-settings-page">
      <PageHeader
        title={t('codeExecution.title')}
        description={t('codeExecution.description')}
      />

      {saved && (
        <SuccessMessage message={t('config.savedSuccess')} />
      )}

      <section
        className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-4"
        data-name="code-execution-controls"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-gray-900 dark:text-white">
              {t('codeExecution.enablePythonRunner')}
            </div>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {t('codeExecution.enablePythonRunnerHelp')}
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={enablePythonRunner}
              onChange={(event) => setEnablePythonRunner(event.target.checked)}
              className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            {enablePythonRunner ? t('common:enabled') : t('common:disabled')}
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium text-gray-900 dark:text-white" htmlFor="execution-timeout-ms">
              {t('codeExecution.executionTimeoutMs')}
            </label>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {t('codeExecution.executionTimeoutMsHelp')}
            </p>
            <input
              id="execution-timeout-ms"
              type="number"
              min={1000}
              step={1000}
              value={executionTimeoutMs}
              onChange={(event) => setExecutionTimeoutMs(event.target.value)}
              className="mt-2 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-gray-900 dark:text-white" htmlFor="max-code-chars">
              {t('codeExecution.maxCodeChars')}
            </label>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {t('codeExecution.maxCodeCharsHelp')}
            </p>
            <input
              id="max-code-chars"
              type="number"
              min={100}
              step={100}
              value={maxCodeChars}
              onChange={(event) => setMaxCodeChars(event.target.value)}
              className="mt-2 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
          >
            {t('config.saveSettings')}
          </button>
          <button
            onClick={handleReset}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md transition-colors"
          >
            {t('codeExecution.resetDefaults')}
          </button>
        </div>
      </section>

      <section
        className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50/60 dark:bg-blue-900/20 p-4 space-y-3"
        data-name="code-execution-usage"
      >
        <div className="text-sm font-semibold text-blue-900 dark:text-blue-300">
          {t('codeExecution.howToUseTitle')}
        </div>
        <ol className="list-decimal pl-5 text-sm text-blue-900/90 dark:text-blue-200 space-y-1">
          <li>{t('codeExecution.howToUseStep1')}</li>
          <li>{t('codeExecution.howToUseStep2')}</li>
          <li>{t('codeExecution.howToUseStep3')}</li>
          <li>{t('codeExecution.howToUseStep4')}</li>
        </ol>
      </section>

      <section
        className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-3"
        data-name="code-execution-test-panel"
      >
        <div className="text-sm font-semibold text-gray-900 dark:text-white">
          {t('codeExecution.testPanelTitle')}
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {t('codeExecution.testPanelDescription')}
        </p>

        <div>
          <div className="mb-2 flex flex-wrap gap-2">
            {codeTemplates.map((template) => (
              <button
                key={template.key}
                type="button"
                onClick={() => setTestCode(template.code)}
                className="px-2.5 py-1 text-xs rounded-md border border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              >
                {template.label}
              </button>
            ))}
          </div>
          <textarea
            ref={testCodeRef}
            value={testCode}
            onChange={(event) => setTestCode(event.target.value)}
            onKeyDown={handleTestCodeKeyDown}
            rows={8}
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-3 py-2 text-sm font-mono text-gray-900 dark:text-gray-100"
          />
          <div className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">
            {testCode.length}/{toPositiveInt(maxCodeChars, initialSettings.maxCodeChars)} chars
          </div>
          {testCodeTooLong && (
            <div className="mt-1 text-xs text-rose-600 dark:text-rose-400">
              {t('codeExecution.testCodeTooLong')}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRunTest}
            disabled={!enablePythonRunner || isRunningTest || testCodeTooLong}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed rounded-md transition-colors"
          >
            {isRunningTest ? t('codeExecution.running') : t('codeExecution.runTest')}
          </button>
          {!enablePythonRunner && (
            <span className="text-xs text-amber-600 dark:text-amber-400">
              {t('codeExecution.testDisabledHint')}
            </span>
          )}
        </div>

        {hasTestOutput && (
          <div className="rounded-md border border-gray-700 bg-gray-950 px-4 py-3 space-y-3" data-name="code-execution-test-output">
            {testStdout && (
              <div>
                <div className="text-[11px] uppercase tracking-wide text-emerald-400 mb-1">stdout</div>
                <pre className="whitespace-pre-wrap break-words text-xs text-emerald-200">{testStdout}</pre>
              </div>
            )}
            {testResult && (
              <div>
                <div className="text-[11px] uppercase tracking-wide text-blue-400 mb-1">result</div>
                <pre className="whitespace-pre-wrap break-words text-xs text-blue-200">{testResult}</pre>
              </div>
            )}
            {testStderr && (
              <div>
                <div className="text-[11px] uppercase tracking-wide text-rose-400 mb-1">stderr</div>
                <pre className="whitespace-pre-wrap break-words text-xs text-rose-200">{testStderr}</pre>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
};
