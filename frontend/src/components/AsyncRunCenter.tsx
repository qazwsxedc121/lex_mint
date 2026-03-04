import React from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { cancelAsyncRun, listAsyncRuns } from '../services/api';
import type { AsyncRunRecord, AsyncRunStatus } from '../services/api';

const ACTIVE_STATUSES: AsyncRunStatus[] = ['queued', 'running'];

const STATUS_STYLE: Record<AsyncRunStatus, string> = {
  queued: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-200',
  running: 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-200',
  succeeded: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200',
  failed: 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-200',
  cancelled: 'bg-gray-200 text-gray-700 dark:bg-gray-600/40 dark:text-gray-200',
};

const STATUS_LABEL: Record<AsyncRunStatus, string> = {
  queued: 'queued',
  running: 'running',
  succeeded: 'succeeded',
  failed: 'failed',
  cancelled: 'cancelled',
};

const formatTimestamp = (value: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '--';
  }
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

const describeRun = (run: AsyncRunRecord): string => {
  if (run.kind === 'workflow') {
    if (run.workflow_id) {
      return `workflow: ${run.workflow_id}`;
    }
    return 'workflow run';
  }
  if (run.session_id) {
    return `chat: ${run.session_id}`;
  }
  return `${run.kind} run`;
};

export const AsyncRunCenter: React.FC = () => {
  const [open, setOpen] = React.useState(false);
  const [runs, setRuns] = React.useState<AsyncRunRecord[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [cancellingRunId, setCancellingRunId] = React.useState<string | null>(null);

  const refreshRuns = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await listAsyncRuns({ limit: 30 });
      setRuns(data);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load runs.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refreshRuns();
    const timer = window.setInterval(() => {
      void refreshRuns();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [refreshRuns]);

  const activeCount = React.useMemo(
    () => runs.filter((run) => ACTIVE_STATUSES.includes(run.status)).length,
    [runs]
  );

  const handleCancel = React.useCallback(async (runId: string) => {
    setCancellingRunId(runId);
    try {
      await cancelAsyncRun(runId);
      await refreshRuns();
    } catch {
      // Ignore cancellation errors; run may already be terminal.
    } finally {
      setCancellingRunId(null);
    }
  }, [refreshRuns]);

  return (
    <div className="fixed bottom-4 right-4 z-40" data-name="async-run-center">
      <div className="flex flex-col items-end gap-2">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="rounded-full border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-md transition hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
          data-name="async-run-center-toggle"
        >
          Runs {activeCount > 0 ? `(${activeCount})` : ''}
        </button>

        {open && (
          <div
            className="w-[360px] max-w-[90vw] rounded-xl border border-gray-200 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-800"
            data-name="async-run-center-panel"
          >
            <div className="flex items-center justify-between border-b border-gray-200 px-3 py-2 dark:border-gray-700" data-name="async-run-center-header">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Run Center</h3>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-gray-100"
                aria-label="Close run center"
                data-name="async-run-center-close"
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="max-h-96 overflow-y-auto p-2" data-name="async-run-center-body">
              {loading && runs.length === 0 ? (
                <p className="px-2 py-3 text-sm text-gray-500 dark:text-gray-400">Loading runs...</p>
              ) : null}
              {error ? (
                <p className="px-2 py-2 text-sm text-red-600 dark:text-red-400">{error}</p>
              ) : null}
              {!loading && runs.length === 0 ? (
                <p className="px-2 py-3 text-sm text-gray-500 dark:text-gray-400">No runs yet.</p>
              ) : null}
              {runs.map((run) => {
                const canCancel = ACTIVE_STATUSES.includes(run.status);
                const isCancelling = cancellingRunId === run.run_id;
                return (
                  <div
                    key={run.run_id}
                    className="mb-2 rounded-lg border border-gray-200 p-2 last:mb-0 dark:border-gray-700"
                    data-name="async-run-center-item"
                  >
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
                        {describeRun(run)}
                      </span>
                      <span className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLE[run.status]}`}>
                        {STATUS_LABEL[run.status]}
                      </span>
                    </div>
                    <p className="mb-1 truncate text-xs text-gray-500 dark:text-gray-400">
                      run_id: {run.run_id}
                    </p>
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {formatTimestamp(run.updated_at)}
                      </p>
                      {canCancel ? (
                        <button
                          type="button"
                          onClick={() => void handleCancel(run.run_id)}
                          disabled={isCancelling}
                          className="rounded border border-red-200 px-2 py-0.5 text-xs text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-600/60 dark:text-red-300 dark:hover:bg-red-500/20"
                          data-name="async-run-center-cancel"
                        >
                          {isCancelling ? 'Cancelling...' : 'Cancel'}
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
