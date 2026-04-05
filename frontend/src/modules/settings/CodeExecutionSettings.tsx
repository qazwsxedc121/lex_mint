import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PageHeader, SuccessMessage } from './components/common';
import {
  getCodeExecutionSettings,
  getDefaultCodeExecutionSettings,
  setCodeExecutionSettings,
  type CodeExecutionSettings,
} from '../../shared/chat/config/codeExecution';

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

  const [enablePythonRunner, setEnablePythonRunner] = useState(initialSettings.enablePythonRunner);
  const [executionTimeoutMs, setExecutionTimeoutMs] = useState(String(initialSettings.executionTimeoutMs));
  const [maxCodeChars, setMaxCodeChars] = useState(String(initialSettings.maxCodeChars));
  const [saved, setSaved] = useState(false);

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
    </div>
  );
};
