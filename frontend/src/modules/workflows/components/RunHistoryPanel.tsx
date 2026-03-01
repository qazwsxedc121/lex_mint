import React from 'react';
import { useTranslation } from 'react-i18next';
import type { WorkflowRunRecord } from '../../../types/workflow';

interface RunHistoryPanelProps {
  runs: WorkflowRunRecord[];
}

const formatTime = (value: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
};

export const RunHistoryPanel: React.FC<RunHistoryPanelProps> = ({ runs }) => {
  const { t } = useTranslation('workflow');
  const [expandedRunId, setExpandedRunId] = React.useState<string | null>(null);

  return (
    <section
      className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-3"
      data-name="workflow-history-panel"
    >
      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('history.title')}</h3>
      {runs.length === 0 ? (
        <div className="text-xs text-gray-500 dark:text-gray-400">{t('history.empty')}</div>
      ) : (
        <ul className="space-y-2 max-h-80 overflow-y-auto">
          {runs.map((run) => (
            <li
              key={run.run_id}
              className="rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 p-2 text-xs"
            >
              <button
                type="button"
                onClick={() => setExpandedRunId((prev) => (prev === run.run_id ? null : run.run_id))}
                className="w-full flex items-center justify-between gap-2 text-left"
              >
                <span className="text-gray-600 dark:text-gray-300">{formatTime(run.started_at)}</span>
                <span className="flex items-center gap-2">
                  <span
                    className={`px-1.5 py-0.5 rounded ${run.status === 'success' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'}`}
                  >
                    {t(`history.status.${run.status}`)}
                  </span>
                  <span className="text-gray-500 dark:text-gray-400">
                    {expandedRunId === run.run_id ? t('history.hideDetails') : t('history.showDetails')}
                  </span>
                </span>
              </button>

              {expandedRunId === run.run_id && (
                <div className="mt-2 space-y-2">
                  <div className="text-[11px] text-gray-500 dark:text-gray-400">
                    {t('history.runId')}: <span className="font-mono">{run.run_id}</span>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[11px] font-medium text-gray-600 dark:text-gray-300">{t('history.inputs')}</div>
                    <pre className="max-h-28 overflow-auto whitespace-pre-wrap break-words rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-2 text-[11px] text-gray-700 dark:text-gray-200">
                      {JSON.stringify(run.inputs ?? {}, null, 2)}
                    </pre>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[11px] font-medium text-gray-600 dark:text-gray-300">{t('history.output')}</div>
                    <pre className="max-h-44 overflow-auto whitespace-pre-wrap break-words rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-2 text-[11px] text-gray-700 dark:text-gray-200">
                      {run.output || '-'}
                    </pre>
                  </div>
                  {run.error && (
                    <div className="space-y-1">
                      <div className="text-[11px] font-medium text-red-600 dark:text-red-300">{t('history.error')}</div>
                      <div className="text-[11px] text-red-600 dark:text-red-300">{run.error}</div>
                    </div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};
