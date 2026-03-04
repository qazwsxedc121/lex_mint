import React from 'react';
import { useTranslation } from 'react-i18next';
import { cancelAsyncRun, runWorkflowStream } from '../../services/api';
import type { Workflow, WorkflowFlowEvent, WorkflowScenario } from '../../types/workflow';
import { useWorkflows } from './hooks/useWorkflows';
import { WorkflowList } from './components/WorkflowList';
import { WorkflowMetaForm } from './components/WorkflowMetaForm';
import { WorkflowEditor } from './components/WorkflowEditor';
import { WorkflowInputSchemaEditor } from './components/WorkflowInputSchemaEditor';
import { WorkflowNodeListEditor } from './components/WorkflowNodeListEditor';
import { WorkflowVisualPanel } from './components/WorkflowVisualPanel';
import { WorkflowRunner } from './components/WorkflowRunner';
import { RunHistoryPanel } from './components/RunHistoryPanel';
import { WorkflowTemplateGallery } from './components/WorkflowTemplateGallery';
import { WORKFLOW_TEMPLATE_PRESETS } from './templates';
import { useWorkflowLauncherStorage } from '../../shared/workflow-launcher/storage';

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
  const [draftInputSchema, setDraftInputSchema] = React.useState<Workflow['input_schema']>([]);
  const [draftEntryNodeId, setDraftEntryNodeId] = React.useState('');
  const [draftNodes, setDraftNodes] = React.useState<Workflow['nodes']>([]);
  const [rawJsonText, setRawJsonText] = React.useState('');
  const [parseError, setParseError] = React.useState<string | null>(null);
  const [runError, setRunError] = React.useState<string | null>(null);
  const [running, setRunning] = React.useState(false);
  const [liveStreamOutput, setLiveStreamOutput] = React.useState('');
  const [finalOutput, setFinalOutput] = React.useState<string | null>(null);
  const [outputMode, setOutputMode] = React.useState<'live' | 'final'>('live');
  const [streamEvents, setStreamEvents] = React.useState<WorkflowFlowEvent[]>([]);
  const [activeView, setActiveView] = React.useState<'builder' | 'playground' | 'history'>('builder');
  const [builderEditorTab, setBuilderEditorTab] = React.useState<'visual' | 'config' | 'json'>('visual');
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
      setDraftInputSchema([]);
      setDraftEntryNodeId('');
      setDraftNodes([]);
      setRawJsonText('');
      setParseError(null);
      return;
    }
    setDraftName(selectedWorkflow.name);
    setDraftDescription(selectedWorkflow.description || '');
    setDraftEnabled(selectedWorkflow.enabled);
    setDraftScenario(selectedWorkflow.scenario);
    setDraftInputSchema(selectedWorkflow.input_schema.map((inputDef) => ({ ...inputDef })));
    setDraftEntryNodeId(selectedWorkflow.entry_node_id);
    setDraftNodes(selectedWorkflow.nodes.map((node) => ({ ...node })));
    setRawJsonText(JSON.stringify({
      input_schema: selectedWorkflow.input_schema,
      entry_node_id: selectedWorkflow.entry_node_id,
      nodes: selectedWorkflow.nodes,
    }, null, 2));
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

  const buildWorkflowConfigPayload = React.useCallback(() => {
    return {
      input_schema: draftInputSchema,
      entry_node_id: draftEntryNodeId,
      nodes: draftNodes,
    };
  }, [draftEntryNodeId, draftInputSchema, draftNodes]);

  const syncRawJsonFromDraft = React.useCallback(() => {
    setRawJsonText(JSON.stringify(buildWorkflowConfigPayload(), null, 2));
  }, [buildWorkflowConfigPayload]);

  const parseRawWorkflowConfig = React.useCallback(() => {
    try {
      const parsed = JSON.parse(rawJsonText) as unknown;
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error(t('errors.parseInvalidJsonObject'));
      }
      const inputSchema = (parsed as { input_schema?: unknown }).input_schema;
      const entryNodeId = (parsed as { entry_node_id?: unknown }).entry_node_id;
      const nodes = (parsed as { nodes?: unknown }).nodes;

      if (!Array.isArray(inputSchema)) {
        throw new Error(t('errors.parseInputSchemaArray'));
      }
      if (typeof entryNodeId !== 'string' || !entryNodeId.trim()) {
        throw new Error(t('errors.parseEntryNode'));
      }
      if (!Array.isArray(nodes)) {
        throw new Error(t('errors.parseNodesArray'));
      }

      return {
        input_schema: inputSchema as Workflow['input_schema'],
        entry_node_id: entryNodeId,
        nodes: nodes as Workflow['nodes'],
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : t('errors.parseInvalidJson');
      setParseError(message);
      return null;
    }
  }, [rawJsonText, t]);

  const handleSave = async () => {
    if (!selectedWorkflow) {
      return;
    }
    if (selectedWorkflow.is_system) {
      setParseError(t('errors.systemReadonly'));
      return;
    }
    const payload =
      builderEditorTab === 'json'
        ? parseRawWorkflowConfig()
        : buildWorkflowConfigPayload();
    if (!payload) {
      return;
    }
    if (!payload.entry_node_id.trim()) {
      setParseError(t('errors.parseEntryNode'));
      return;
    }
    if (!payload.nodes.length) {
      setParseError(t('errors.parseNodesArray'));
      return;
    }
    setParseError(null);
    await updateWorkflow(selectedWorkflow.id, {
      name: draftName,
      description: draftDescription || null,
      enabled: draftEnabled,
      scenario: draftScenario,
      input_schema: payload.input_schema,
      entry_node_id: payload.entry_node_id,
      nodes: payload.nodes,
    });
    setDraftInputSchema(payload.input_schema);
    setDraftEntryNodeId(payload.entry_node_id);
    setDraftNodes(payload.nodes);
    setRawJsonText(JSON.stringify(payload, null, 2));
  };

  const entryNodeOptions = React.useMemo(() => {
    const ids: string[] = [];
    const seen = new Set<string>();
    draftNodes.forEach((node) => {
      const id = node.id.trim();
      if (!id || seen.has(id)) {
        return;
      }
      seen.add(id);
      ids.push(id);
    });
    return ids;
  }, [draftNodes]);

  const visualDslText = React.useMemo(() => {
    return JSON.stringify({
      entry_node_id: draftEntryNodeId,
      nodes: draftNodes,
    });
  }, [draftEntryNodeId, draftNodes]);

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

                <div className="space-y-3" data-name="workflows-builder-editors">
                  <div className="flex items-center justify-between gap-3">
                    <div className="inline-flex rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-1">
                      <button
                        type="button"
                        data-name="workflow-builder-tab-visual"
                        onClick={() => setBuilderEditorTab('visual')}
                        className={`rounded-md px-3 py-1.5 text-sm ${
                          builderEditorTab === 'visual'
                            ? 'bg-blue-600 text-white'
                            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                        }`}
                      >
                        {t('builderEditorTab.visual')}
                      </button>
                      <button
                        type="button"
                        data-name="workflow-builder-tab-config"
                        onClick={() => setBuilderEditorTab('config')}
                        className={`rounded-md px-3 py-1.5 text-sm ${
                          builderEditorTab === 'config'
                            ? 'bg-blue-600 text-white'
                            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                        }`}
                      >
                        {t('builderEditorTab.config')}
                      </button>
                      <button
                        type="button"
                        data-name="workflow-builder-tab-json"
                        onClick={() => {
                          syncRawJsonFromDraft();
                          setBuilderEditorTab('json');
                        }}
                        className={`rounded-md px-3 py-1.5 text-sm ${
                          builderEditorTab === 'json'
                            ? 'bg-blue-600 text-white'
                            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                        }`}
                      >
                        {t('builderEditorTab.json')}
                      </button>
                    </div>
                    <button
                      type="button"
                      data-name="workflow-builder-save"
                      onClick={handleSave}
                      disabled={saving || isSelectedSystemWorkflow}
                      className="rounded-md px-3 py-1.5 text-xs font-medium bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-60"
                    >
                      {saving ? t('actions.saving') : t('actions.save')}
                    </button>
                  </div>

                  {builderEditorTab === 'visual' ? (
                    <WorkflowVisualPanel dslText={visualDslText} />
                  ) : builderEditorTab === 'config' ? (
                    <div className="space-y-4">
                      <WorkflowInputSchemaEditor
                        inputs={draftInputSchema}
                        disabled={isSelectedSystemWorkflow}
                        onChange={(nextInputs) => {
                          setDraftInputSchema(nextInputs);
                          if (parseError) {
                            setParseError(null);
                          }
                        }}
                      />

                      <section
                        className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-2"
                        data-name="workflow-entry-node-editor"
                      >
                        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                          {t('entryNodeEditor.title')}
                        </h3>
                        <label className="space-y-1 block">
                          <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
                            {t('entryNodeEditor.label')}
                          </span>
                          <select
                            data-name="workflow-entry-node-select"
                            value={draftEntryNodeId}
                            disabled={isSelectedSystemWorkflow}
                            onChange={(event) => {
                              setDraftEntryNodeId(event.target.value);
                              if (parseError) {
                                setParseError(null);
                              }
                            }}
                            className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 disabled:opacity-60"
                          >
                            {!draftEntryNodeId && (
                              <option value="">{t('entryNodeEditor.placeholder')}</option>
                            )}
                            {entryNodeOptions.map((nodeId) => (
                              <option key={nodeId} value={nodeId}>
                                {nodeId}
                              </option>
                            ))}
                            {draftEntryNodeId && !entryNodeOptions.includes(draftEntryNodeId) && (
                              <option value={draftEntryNodeId}>{draftEntryNodeId}</option>
                            )}
                          </select>
                        </label>
                        {entryNodeOptions.length === 0 && (
                          <div className="text-xs text-amber-700 dark:text-amber-300">
                            {t('entryNodeEditor.noNodesHint')}
                          </div>
                        )}
                      </section>

                      <WorkflowNodeListEditor
                        nodes={draftNodes}
                        disabled={isSelectedSystemWorkflow}
                        onChange={(nextNodes) => {
                          setDraftNodes(nextNodes);
                          if (parseError) {
                            setParseError(null);
                          }
                        }}
                      />

                      {parseError && (
                        <div
                          className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300"
                          data-name="workflow-builder-parse-error"
                        >
                          {parseError}
                        </div>
                      )}
                    </div>
                  ) : (
                    <WorkflowEditor
                      title={t('editor.configTitle')}
                      value={rawJsonText}
                      parseError={parseError}
                      saving={saving}
                      readOnly={isSelectedSystemWorkflow}
                      showSaveButton={false}
                      onChange={(value) => {
                        setRawJsonText(value);
                        if (parseError) {
                          setParseError(null);
                        }
                      }}
                      onSave={handleSave}
                    />
                  )}
                </div>
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
