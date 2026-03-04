import React from 'react';
import { useTranslation } from 'react-i18next';
import { cancelAsyncRun, runWorkflowStream } from '../../services/api';
import type { Workflow, WorkflowFlowEvent, WorkflowScenario } from '../../types/workflow';
import { useWorkflows } from './hooks/useWorkflows';
import { WorkflowList } from './components/WorkflowList';
import { WorkflowMetaForm } from './components/WorkflowMetaForm';
import { WorkflowEditor } from './components/WorkflowEditor';
import { WorkflowRunner } from './components/WorkflowRunner';
import { RunHistoryPanel } from './components/RunHistoryPanel';
import { WorkflowTemplateGallery } from './components/WorkflowTemplateGallery';
import { WORKFLOW_TEMPLATE_PRESETS } from './templates';
import { useWorkflowLauncherStorage } from '../../shared/workflow-launcher/storage';

const stringifyDsl = (workflow: Workflow): string => {
  return JSON.stringify(
    {
      input_schema: workflow.input_schema,
      entry_node_id: workflow.entry_node_id,
      nodes: workflow.nodes,
    },
    null,
    2
  );
};

export const WorkflowsModule: React.FC = () => {
  const { t } = useTranslation('workflow');
  const { favoritesSet: launcherFavorites, recents: launcherRecents, toggleFavorite: toggleLauncherFavorite, addRecent: addLauncherRecent } = useWorkflowLauncherStorage();
  const {
    workflows,
    selectedWorkflowId,
    setSelectedWorkflowId,
    runs,
    loading,
    saving,
    error,
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
    refreshRuns,
  } = useWorkflows();

  const selectedWorkflow = React.useMemo(
    () => workflows.find((item) => item.id === selectedWorkflowId) ?? null,
    [selectedWorkflowId, workflows]
  );
  const enabledWorkflows = React.useMemo(
    () => workflows.filter((item) => item.enabled),
    [workflows]
  );
  const playgroundWorkflow = React.useMemo(() => {
    if (selectedWorkflow && selectedWorkflow.enabled) {
      return selectedWorkflow;
    }
    return enabledWorkflows[0] ?? null;
  }, [enabledWorkflows, selectedWorkflow]);
  const isSelectedSystemWorkflow = Boolean(selectedWorkflow?.is_system);

  const [draftName, setDraftName] = React.useState('');
  const [draftDescription, setDraftDescription] = React.useState('');
  const [draftEnabled, setDraftEnabled] = React.useState(true);
  const [draftScenario, setDraftScenario] = React.useState<WorkflowScenario>('general');
  const [dslText, setDslText] = React.useState('');
  const [parseError, setParseError] = React.useState<string | null>(null);
  const [runError, setRunError] = React.useState<string | null>(null);
  const [running, setRunning] = React.useState(false);
  const [liveStreamOutput, setLiveStreamOutput] = React.useState('');
  const [finalOutput, setFinalOutput] = React.useState<string | null>(null);
  const [outputMode, setOutputMode] = React.useState<'live' | 'final'>('live');
  const [streamEvents, setStreamEvents] = React.useState<WorkflowFlowEvent[]>([]);
  const [activeView, setActiveView] = React.useState<'builder' | 'playground' | 'history'>('builder');
  const [activeRunId, setActiveRunId] = React.useState<string | null>(null);
  const abortControllerRef = React.useRef<AbortController | null>(null);
  const liveOutputRef = React.useRef('');
  const hasFinalOutputRef = React.useRef(false);

  React.useEffect(() => {
    if (!selectedWorkflow) {
      setDraftName('');
      setDraftDescription('');
      setDraftEnabled(true);
      setDraftScenario('general');
      setDslText('');
      setParseError(null);
      return;
    }
    setDraftName(selectedWorkflow.name);
    setDraftDescription(selectedWorkflow.description || '');
    setDraftEnabled(selectedWorkflow.enabled);
    setDraftScenario(selectedWorkflow.scenario);
    setDslText(stringifyDsl(selectedWorkflow));
    setParseError(null);
  }, [selectedWorkflow]);

  const handleCreate = async () => {
    await createWorkflow();
  };

  const handleUseTemplate = async (template: (typeof WORKFLOW_TEMPLATE_PRESETS)[number]) => {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    await createWorkflow({
      ...template.workflow,
      name: `${t(template.workflowNameKey, template.workflow.name)} ${timestamp}`,
      description: t(template.workflowDescriptionKey, template.workflow.description || ''),
    });
  };

  const handleDelete = async (workflowId: string) => {
    const target = workflows.find((item) => item.id === workflowId);
    if (target?.is_system) {
      setParseError(t('errors.systemReadonly'));
      return;
    }
    const confirmed = window.confirm(t('deleteConfirm'));
    if (!confirmed) {
      return;
    }
    await deleteWorkflow(workflowId);
  };

  const parseDsl = React.useCallback(() => {
    try {
      const parsed = JSON.parse(dslText) as {
        input_schema: Workflow['input_schema'];
        entry_node_id: Workflow['entry_node_id'];
        nodes: Workflow['nodes'];
      };

      if (!parsed || typeof parsed !== 'object') {
        throw new Error(t('errors.parseInvalidJsonObject'));
      }
      if (!Array.isArray(parsed.input_schema)) {
        throw new Error(t('errors.parseInputSchemaArray'));
      }
      if (!Array.isArray(parsed.nodes)) {
        throw new Error(t('errors.parseNodesArray'));
      }
      if (typeof parsed.entry_node_id !== 'string' || !parsed.entry_node_id.trim()) {
        throw new Error(t('errors.parseEntryNode'));
      }

      setParseError(null);
      return parsed;
    } catch (err) {
      const message = err instanceof Error ? err.message : t('errors.parseInvalidJson');
      setParseError(message);
      return null;
    }
  }, [dslText, t]);

  const handleSave = async () => {
    if (!selectedWorkflow) {
      return;
    }
    if (selectedWorkflow.is_system) {
      setParseError(t('errors.systemReadonly'));
      return;
    }
    const parsedDsl = parseDsl();
    if (!parsedDsl) {
      return;
    }
    await updateWorkflow(selectedWorkflow.id, {
      name: draftName,
      description: draftDescription || null,
      enabled: draftEnabled,
      scenario: draftScenario,
      input_schema: parsedDsl.input_schema,
      entry_node_id: parsedDsl.entry_node_id,
      nodes: parsedDsl.nodes,
    });
  };

  const handleRun = React.useCallback(async (workflowId: string, inputs: Record<string, unknown>) => {
    const workflow = workflows.find((item) => item.id === workflowId) ?? null;
    if (!workflow) {
      return;
    }

    setRunError(null);
    setLiveStreamOutput('');
    liveOutputRef.current = '';
    setFinalOutput(null);
    setOutputMode('live');
    hasFinalOutputRef.current = false;
    setStreamEvents([]);
    setRunning(true);
    setActiveRunId(null);
    try {
      await runWorkflowStream(
        workflow.id,
        inputs,
        {
          onRunCreated: (runId) => {
            setActiveRunId(runId);
          },
          onEvent: (event) => {
            if (event.event_type === 'workflow_output_reported' || event.event_type === 'workflow_run_finished') {
              const finalOutput = event.payload.output;
              if (typeof finalOutput === 'string') {
                setFinalOutput(finalOutput);
                hasFinalOutputRef.current = true;
                setOutputMode('final');
              } else if (event.event_type === 'workflow_run_finished') {
                setFinalOutput(liveOutputRef.current);
                setOutputMode('final');
              }
            }
            if (event.event_type === 'text_delta') {
              return;
            }
            setStreamEvents((prev) => [...prev.slice(-199), event]);
          },
          onChunk: (chunk) => {
            setLiveStreamOutput((prev) => {
              const next = prev + chunk;
              liveOutputRef.current = next;
              return next;
            });
          },
          onError: (message) => {
            setRunError(message);
            setActiveRunId(null);
          },
          onComplete: () => {
            addLauncherRecent(workflow.id);
            setActiveRunId(null);
            void (async () => {
              const latestRuns = await refreshRuns(workflow.id);
              if (!hasFinalOutputRef.current) {
                const historyOutput = latestRuns[0]?.output;
                if (typeof historyOutput === 'string') {
                  setFinalOutput(historyOutput);
                } else {
                  setFinalOutput(liveOutputRef.current);
                }
              }
              setOutputMode('final');
            })();
          },
        },
        abortControllerRef
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : t('errors.runRequestFailed');
      setRunError(message);
      setActiveRunId(null);
    } finally {
      setRunning(false);
      void refreshRuns(workflow.id);
    }
  }, [addLauncherRecent, refreshRuns, t, workflows]);

  const handleStop = React.useCallback(() => {
    abortControllerRef.current?.abort();
    setRunning(false);
    const runId = activeRunId;
    setActiveRunId(null);
    if (!runId) {
      return;
    }
    void cancelAsyncRun(runId).catch(() => {
      // Run may already be terminal when stop is pressed.
    });
  }, [activeRunId]);

  return (
    <div className="flex flex-1 bg-gray-100 dark:bg-gray-900" data-name="workflows-module">
      <main className="flex-1 overflow-y-auto p-6">
        <div className="space-y-4">
          <header className="flex flex-col gap-1" data-name="workflows-header">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{t('title')}</h2>
            <p className="text-sm text-gray-600 dark:text-gray-300">{t('description')}</p>
          </header>

          <div className="inline-flex rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-1" data-name="workflows-view-switch">
            <button
              type="button"
              onClick={() => setActiveView('builder')}
              className={`rounded-md px-3 py-1.5 text-sm ${
                activeView === 'builder'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {t('view.builder')}
            </button>
            <button
              type="button"
              onClick={() => setActiveView('playground')}
              className={`rounded-md px-3 py-1.5 text-sm ${
                activeView === 'playground'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {t('view.playground')}
            </button>
            <button
              type="button"
              onClick={() => setActiveView('history')}
              className={`rounded-md px-3 py-1.5 text-sm ${
                activeView === 'history'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {t('view.history')}
            </button>
          </div>

          {error && (
            <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300" data-name="workflows-error">
              {error}
            </div>
          )}

          {activeView === 'builder' ? (
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-4" data-name="workflows-builder-layout">
              <div className="xl:col-span-4">
                <div className="space-y-4">
                  <WorkflowList
                    workflows={workflows}
                    selectedWorkflowId={selectedWorkflowId}
                    loading={loading}
                    saving={saving}
                    editable
                    favorites={launcherFavorites}
                    recents={launcherRecents}
                    onSelect={setSelectedWorkflowId}
                    onToggleFavorite={toggleLauncherFavorite}
                    onCreate={handleCreate}
                    onDelete={handleDelete}
                  />
                  <WorkflowTemplateGallery
                    templates={WORKFLOW_TEMPLATE_PRESETS}
                    creating={saving}
                    onUseTemplate={handleUseTemplate}
                  />
                </div>
              </div>

              <div className="xl:col-span-8 space-y-4">
                <section className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4" data-name="workflow-meta-panel">
                  <WorkflowMetaForm
                    name={draftName}
                    description={draftDescription}
                    enabled={draftEnabled}
                    scenario={draftScenario}
                    disabled={isSelectedSystemWorkflow}
                    onNameChange={setDraftName}
                    onDescriptionChange={setDraftDescription}
                    onEnabledChange={setDraftEnabled}
                    onScenarioChange={setDraftScenario}
                  />
                </section>
                <WorkflowEditor
                  value={dslText}
                  parseError={parseError}
                  saving={saving}
                  readOnly={isSelectedSystemWorkflow}
                  onChange={(value) => {
                    setDslText(value);
                    if (parseError) {
                      setParseError(null);
                    }
                  }}
                  onSave={handleSave}
                />
              </div>
            </div>
          ) : activeView === 'playground' ? (
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-4" data-name="workflows-playground-layout">
              <div className="xl:col-span-4">
                <WorkflowList
                  workflows={enabledWorkflows}
                  selectedWorkflowId={playgroundWorkflow?.id ?? null}
                  loading={loading}
                  saving={saving}
                  selectionLocked={running}
                  editable={false}
                  favorites={launcherFavorites}
                  recents={launcherRecents}
                  onSelect={setSelectedWorkflowId}
                  onToggleFavorite={toggleLauncherFavorite}
                  onCreate={handleCreate}
                  onDelete={handleDelete}
                />
              </div>

              <div className="xl:col-span-8 space-y-4">
                {playgroundWorkflow ? (
                  <WorkflowRunner
                    workflow={playgroundWorkflow}
                    running={running}
                    outputMode={running ? 'live' : outputMode}
                    streamOutput={
                      running ? liveStreamOutput : (outputMode === 'final' ? (finalOutput ?? liveStreamOutput) : liveStreamOutput)
                    }
                    runError={runError}
                    events={streamEvents}
                    onRun={handleRun}
                    onStop={handleStop}
                  />
                ) : (
                  <section
                    className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4"
                    data-name="workflows-playground-empty"
                  >
                    <p className="text-sm text-gray-600 dark:text-gray-300">{t('playground.noEnabledWorkflows')}</p>
                  </section>
                )}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-4" data-name="workflows-history-layout">
              <div className="xl:col-span-4">
                <WorkflowList
                  workflows={workflows}
                  selectedWorkflowId={selectedWorkflowId}
                  loading={loading}
                  saving={saving}
                  editable={false}
                  favorites={launcherFavorites}
                  recents={launcherRecents}
                  onSelect={setSelectedWorkflowId}
                  onToggleFavorite={toggleLauncherFavorite}
                  onCreate={handleCreate}
                  onDelete={handleDelete}
                />
              </div>

              <div className="xl:col-span-8">
                <RunHistoryPanel runs={runs} />
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
