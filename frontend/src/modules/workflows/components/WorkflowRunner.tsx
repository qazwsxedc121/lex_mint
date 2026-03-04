import React from 'react';
import { useTranslation } from 'react-i18next';
import type { Workflow, WorkflowFlowEvent } from '../../../types/workflow';

interface WorkflowRunnerProps {
  workflow: Workflow | null;
  running: boolean;
  outputMode: 'live' | 'final';
  streamOutput: string;
  runError: string | null;
  events: WorkflowFlowEvent[];
  onRun: (workflowId: string, inputs: Record<string, unknown>) => void;
  onStop: () => void;
}

export const WorkflowRunner: React.FC<WorkflowRunnerProps> = ({
  workflow,
  running,
  outputMode,
  streamOutput,
  runError,
  events,
  onRun,
  onStop,
}) => {
  const { t } = useTranslation('workflow');
  const [inputs, setInputs] = React.useState<Record<string, unknown>>({});
  const [showDebugEvents, setShowDebugEvents] = React.useState(false);
  const [showEventDetails, setShowEventDetails] = React.useState(false);

  React.useEffect(() => {
    if (!workflow) {
      setInputs({});
      return;
    }
    const defaults: Record<string, unknown> = {};
    workflow.input_schema.forEach((field) => {
      if (field.default !== undefined) {
        defaults[field.key] = field.default;
      }
    });
    setInputs(defaults);
  }, [workflow]);

  const updateInput = (key: string, value: unknown) => {
    setInputs((prev) => ({ ...prev, [key]: value }));
  };

  const timelineEvents = React.useMemo(() => {
    return events
      .map((event) => {
        const payload = event.payload || {};
        const nodeId = typeof payload.node_id === 'string' ? payload.node_id : '';
        const nodeType = typeof payload.node_type === 'string' ? payload.node_type : '';

        switch (event.event_type) {
          case 'workflow_run_started':
            return `${t('runner.event.workflowRunStarted')}`;
          case 'workflow_node_started':
            return `${t('runner.event.workflowNodeStarted')} ${nodeId} (${nodeType || '-'})`;
          case 'workflow_node_finished':
            return `${t('runner.event.workflowNodeFinished')} ${nodeId} (${nodeType || '-'})`;
          case 'workflow_condition_evaluated': {
            const result = payload.result === true ? t('runner.boolTrue') : t('runner.boolFalse');
            return `${t('runner.event.workflowConditionEvaluated')} ${nodeId}: ${result}`;
          }
          case 'workflow_run_finished':
            return `${t('runner.event.workflowRunFinished')}`;
          case 'workflow_artifact_written': {
            const filePath = typeof payload.file_path === 'string' ? payload.file_path : '-';
            return `${t('runner.event.workflowArtifactWritten')}: ${filePath}`;
          }
          case 'stream_error': {
            const errorText = typeof payload.error === 'string' ? payload.error : t('errors.runFailed');
            return `${t('runner.event.streamError')}: ${errorText}`;
          }
          default:
            return null;
        }
      })
      .filter((value): value is string => Boolean(value));
  }, [events, t]);

  const currentNode = React.useMemo(() => {
    let active: { nodeId: string; nodeType: string } | null = null;

    for (const event of events) {
      const payload = event.payload || {};
      const nodeId = typeof payload.node_id === 'string' ? payload.node_id : '';
      const nodeType = typeof payload.node_type === 'string' ? payload.node_type : '-';

      if (event.event_type === 'workflow_node_started') {
        active = { nodeId, nodeType };
        continue;
      }

      if (event.event_type === 'workflow_node_finished' && active && active.nodeId === nodeId) {
        active = null;
      }
    }

    return active;
  }, [events]);

  const statusText = React.useMemo(() => {
    if (running) {
      if (currentNode) {
        return `${currentNode.nodeId} (${currentNode.nodeType})`;
      }
      return t('runner.preparing');
    }
    return t('runner.idle');
  }, [currentNode, running, t]);

  return (
    <section
      className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-3"
      data-name="workflow-runner-panel"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('runner.title')}</h3>
        {!running ? (
          <button
            type="button"
            onClick={() => {
              if (workflow) {
                onRun(workflow.id, inputs);
              }
            }}
            disabled={!workflow}
            className="rounded-md px-3 py-1.5 text-xs font-medium bg-green-600 text-white hover:bg-green-500 disabled:opacity-60"
          >
            {t('actions.run')}
          </button>
        ) : (
          <button
            type="button"
            onClick={onStop}
            className="rounded-md px-3 py-1.5 text-xs font-medium bg-red-600 text-white hover:bg-red-500"
          >
            {t('actions.stop')}
          </button>
        )}
      </div>

      {workflow && workflow.input_schema.length > 0 && (
        <div className="space-y-2" data-name="workflow-runner-inputs">
          {workflow.input_schema.map((field) => (
            <label key={field.key} className="block space-y-1">
              <span className="text-xs text-gray-600 dark:text-gray-300">
                {field.key}
                {field.required ? ' *' : ''}
              </span>
              {field.type === 'boolean' ? (
                <select
                  value={String(inputs[field.key] ?? false)}
                  onChange={(event) => updateInput(field.key, event.target.value === 'true')}
                  className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-sm text-gray-900 dark:text-gray-100"
                >
                  <option value="true">{t('runner.boolTrue')}</option>
                  <option value="false">{t('runner.boolFalse')}</option>
                </select>
              ) : (
                <input
                  value={String(inputs[field.key] ?? '')}
                  onChange={(event) => {
                    const rawValue = event.target.value;
                    if (field.type === 'number') {
                      updateInput(field.key, rawValue === '' ? '' : Number(rawValue));
                    } else {
                      updateInput(field.key, rawValue);
                    }
                  }}
                  type={field.type === 'number' ? 'number' : 'text'}
                  className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-sm text-gray-900 dark:text-gray-100"
                />
              )}
            </label>
          ))}
        </div>
      )}

      {runError && (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300" data-name="workflow-runner-error">
          {runError}
        </div>
      )}

      <div className="space-y-2" data-name="workflow-runner-output">
        <div className="text-xs font-medium text-gray-600 dark:text-gray-300">
          {outputMode === 'final' ? t('runner.finalOutput') : t('runner.liveOutput')}
        </div>
        <pre className="min-h-24 max-h-40 overflow-auto rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 p-2 text-xs text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words">
          {streamOutput || (running ? t('runner.running') : '-')}
        </pre>
      </div>

      <div className="space-y-2" data-name="workflow-runner-events">
        <button
          type="button"
          onClick={() => setShowEventDetails((prev) => !prev)}
          className="w-full flex items-center justify-between gap-2 rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 px-3 py-2 text-sm text-gray-800 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700"
        >
          <span className="flex items-center gap-2 min-w-0">
            <span className={`inline-block h-2 w-2 rounded-full ${running ? 'bg-emerald-500' : 'bg-gray-400 dark:bg-gray-500'}`} />
            <span className="truncate font-mono">{statusText}</span>
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400">{showEventDetails ? '▲' : '▼'}</span>
        </button>

        {showEventDetails && (
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => setShowDebugEvents((prev) => !prev)}
              className="rounded px-2 py-1 text-[11px] border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              {showDebugEvents ? t('runner.hideDebug') : t('runner.showDebug')}
            </button>
            <div className="max-h-40 overflow-auto rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 p-2">
            {!showDebugEvents ? (
              timelineEvents.length === 0 ? (
                <div className="text-xs text-gray-500 dark:text-gray-400">{t('runner.emptyEvents')}</div>
              ) : (
                <ul className="space-y-1">
                  {timelineEvents.map((line, index) => (
                    <li key={`${index}-${line}`} className="text-xs text-gray-700 dark:text-gray-300">
                      {line}
                    </li>
                  ))}
                </ul>
              )
            ) : (
              events.length === 0 ? (
                <div className="text-xs text-gray-500 dark:text-gray-400">{t('runner.emptyEvents')}</div>
              ) : (
                <ul className="space-y-1">
                  {events.map((event) => (
                    <li key={event.event_id} className="text-xs text-gray-700 dark:text-gray-300">
                      {event.event_type}
                    </li>
                  ))}
                </ul>
              )
            )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
