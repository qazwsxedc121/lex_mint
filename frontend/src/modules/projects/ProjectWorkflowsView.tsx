import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BoltIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { useNavigate, useOutletContext } from 'react-router-dom';
import {
  addProjectWorkspaceItem,
  cancelAsyncRun,
  getAsyncRun,
  listAsyncRuns,
  listWorkflows,
  runWorkflowStream,
  type AsyncRunRecord,
} from '../../services/api';
import type { Workflow } from '../../types/workflow';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import { useWorkflowLauncherStorage } from '../../shared/workflow-launcher/storage';
import type { LauncherRecommendationContext } from '../../shared/workflow-launcher/types';
import { ProjectWorkflowPanel } from './components/ProjectWorkflowPanel';
import {
  applyProjectWorkflowLaunchContext,
  buildProjectWorkflowDefaultInputs,
  getWorkflowNodeIds,
  validateProjectWorkflowInputs,
} from './projectWorkflowUtils';
import type { ProjectWorkflowLaunchContext, ProjectWorkspaceOutletContext } from './workspace';

const formatRunTime = (value: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
};

const truncateRunError = (value: string, maxLength = 140): string => {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 1)}...`;
};

export const ProjectWorkflowsView: React.FC = () => {
  const { t } = useTranslation('projects');
  const navigate = useNavigate();
  const { projectId, currentProject } = useOutletContext<ProjectWorkspaceOutletContext>();
  const {
    getCurrentFile,
    getProjectSession,
    consumeWorkflowLaunch,
  } = useProjectWorkspaceStore();
  const { favoritesSet, recents, toggleFavorite, addRecent } = useWorkflowLauncherStorage();
  const [workflowsLoading, setWorkflowsLoading] = useState(true);
  const [workflowLoadError, setWorkflowLoadError] = useState<string | null>(null);
  const [allWorkflows, setAllWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState('');
  const [inputValues, setInputValues] = useState<Record<string, unknown>>({});
  const [artifactPath, setArtifactPath] = useState('');
  const [writeMode, setWriteMode] = useState<'none' | 'create' | 'overwrite'>('overwrite');
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [output, setOutput] = useState('');
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [recentRuns, setRecentRuns] = useState<AsyncRunRecord[]>([]);
  const [recentRunsLoading, setRecentRunsLoading] = useState(false);
  const [recentRunsError, setRecentRunsError] = useState<string | null>(null);
  const [launchContext, setLaunchContext] = useState<ProjectWorkflowLaunchContext | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const launchAppliedRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const currentFilePath = getCurrentFile(projectId);
  const currentSessionId = getProjectSession(projectId);

  const projectWorkflows = useMemo(
    () => allWorkflows.filter((workflow) => workflow.enabled && workflow.scenario === 'project_pipeline'),
    [allWorkflows]
  );

  const activeWorkflow = useMemo(() => {
    if (projectWorkflows.length === 0) {
      return null;
    }
    return projectWorkflows.find((workflow) => workflow.id === selectedWorkflowId) || projectWorkflows[0];
  }, [projectWorkflows, selectedWorkflowId]);

  const workflowInputDefs = useMemo(() => activeWorkflow?.input_schema || [], [activeWorkflow]);
  const workflowNodeIds = useMemo(() => getWorkflowNodeIds(activeWorkflow), [activeWorkflow]);
  const recommendationContext = useMemo<LauncherRecommendationContext>(
    () => ({
      module: 'projects',
      requiredScenario: 'project_pipeline',
      filePath: launchContext?.filePath || currentFilePath || undefined,
      hasSelection: Boolean(launchContext?.selectedText?.trim()),
    }),
    [currentFilePath, launchContext]
  );

  const workflowNameMap = useMemo(() => {
    const next = new Map<string, string>();
    allWorkflows.forEach((workflow) => {
      next.set(workflow.id, workflow.name);
    });
    return next;
  }, [allWorkflows]);

  const loadRecentRuns = useCallback(async () => {
    setRecentRunsLoading(true);
    setRecentRunsError(null);
    try {
      const runs = await listAsyncRuns({
        limit: 8,
        kind: 'workflow',
        contextType: 'project',
        projectId,
      });
      setRecentRuns(runs);
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || t('workspace.workflows.recentRunsLoadFailed');
      setRecentRunsError(String(message));
      setRecentRuns([]);
    } finally {
      setRecentRunsLoading(false);
    }
  }, [projectId, t]);

  useEffect(() => {
    let disposed = false;
    setWorkflowsLoading(true);
    setWorkflowLoadError(null);
    void (async () => {
      try {
        const workflows = await listWorkflows();
        if (disposed) {
          return;
        }
        setAllWorkflows(workflows);
      } catch (err) {
        if (disposed) {
          return;
        }
        console.error('Failed to load project workflows:', err);
        setWorkflowLoadError(t('projectWorkflow.loadWorkflowsFailed'));
        setAllWorkflows([]);
      } finally {
        if (!disposed) {
          setWorkflowsLoading(false);
        }
      }
    })();

    return () => {
      disposed = true;
    };
  }, [t]);

  useEffect(() => {
    launchAppliedRef.current = false;
    setLaunchContext(consumeWorkflowLaunch(projectId));
  }, [consumeWorkflowLaunch, projectId]);

  useEffect(() => {
    void loadRecentRuns();
  }, [loadRecentRuns]);

  useEffect(() => {
    setSelectedWorkflowId((previous) => {
      if (previous && projectWorkflows.some((workflow) => workflow.id === previous)) {
        return previous;
      }
      return projectWorkflows[0]?.id || '';
    });
  }, [projectWorkflows]);

  useEffect(() => {
    if (!activeWorkflow) {
      setInputValues({});
      return;
    }

    const nextInputs = applyProjectWorkflowLaunchContext(
      activeWorkflow,
      buildProjectWorkflowDefaultInputs(activeWorkflow),
      launchAppliedRef.current ? null : launchContext,
      projectId,
      currentSessionId
    );
    setInputValues(nextInputs);

    if (launchContext && !launchAppliedRef.current) {
      launchAppliedRef.current = true;
      setLaunchContext(null);
    }
  }, [activeWorkflow, currentSessionId, launchContext, projectId]);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
    };
  }, []);

  const handleWorkflowChange = useCallback((workflowId: string) => {
    if (running) {
      return;
    }
    setSelectedWorkflowId(workflowId);
    setRunError(null);
    setOutput('');
  }, [running]);

  const handleInputChange = useCallback((key: string, value: unknown) => {
    setInputValues((previous) => {
      const next = { ...previous };
      if (value === undefined) {
        delete next[key];
      } else {
        next[key] = value;
      }
      return next;
    });
  }, []);

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setRunning(false);
    const runId = activeRunId;
    setActiveRunId(null);
    if (!runId) {
      return;
    }
    void cancelAsyncRun(runId).catch(() => {
      // Ignore cancellation race if run already completed.
    });
  }, [activeRunId]);

  const handleRun = useCallback(async () => {
    if (running || !activeWorkflow) {
      return;
    }

    const prepared = validateProjectWorkflowInputs(activeWorkflow, inputValues, t);
    if (prepared.error) {
      setRunError(prepared.error);
      return;
    }

    setRunning(true);
    setRunError(null);
    setOutput('');
    setActiveRunId(null);

    const normalizedArtifactPath = artifactPath.trim();
    let createdRunId: string | null = null;

    const syncRunWorkspaceItem = async (runId: string) => {
      const latestRun = await getAsyncRun(runId);
      await addProjectWorkspaceItem(projectId, {
        type: 'run',
        id: latestRun.run_id,
        title: activeWorkflow.name || latestRun.workflow_id || t('workspace.workflows.unknownWorkflow'),
        meta: {
          workflow_id: latestRun.workflow_id,
          status: latestRun.status,
          artifact_path: latestRun.result_summary?.artifact_path,
        },
      });
    };

    try {
      await runWorkflowStream(
        activeWorkflow.id,
        prepared.inputs,
        {
          onRunCreated: (runId) => {
            createdRunId = runId;
            setActiveRunId(runId);
            void addProjectWorkspaceItem(projectId, {
              type: 'run',
              id: runId,
              title: activeWorkflow.name || activeWorkflow.id,
              meta: {
                workflow_id: activeWorkflow.id,
                status: 'queued',
              },
            }).catch((error) => {
              console.error('Failed to persist queued project workflow run:', error);
            });
          },
          onEvent: (event) => {
            if (event.event_type !== 'workflow_artifact_written') {
              return;
            }
            const writtenPath = event.payload.file_path;
            const written = event.payload.written === true;
            if (typeof writtenPath !== 'string' || !writtenPath.trim()) {
              return;
            }
            setOutput((previous) => {
              const prefix = previous ? `${previous}\n\n` : '';
              return `${prefix}[artifact] ${writtenPath}`;
            });
            if (written) {
              window.dispatchEvent(new CustomEvent('project-tree-updated', {
                detail: { projectId, filePath: writtenPath },
              }));
            }
          },
          onChunk: (chunk) => {
            setOutput((previous) => previous + chunk);
          },
          onComplete: () => {
            setRunning(false);
            setActiveRunId(null);
            addRecent(activeWorkflow.id);
            if (createdRunId) {
              void syncRunWorkspaceItem(createdRunId).catch((error) => {
                console.error('Failed to persist completed project workflow run:', error);
              });
            }
            void loadRecentRuns();
          },
          onError: (message) => {
            setRunning(false);
            setActiveRunId(null);
            setRunError(message);
            if (createdRunId) {
              void syncRunWorkspaceItem(createdRunId).catch((error) => {
                console.error('Failed to persist failed project workflow run:', error);
              });
            }
            void loadRecentRuns();
          },
        },
        abortControllerRef,
        {
          sessionId: currentSessionId || undefined,
          contextType: 'project',
          projectId,
          streamMode: 'default',
          artifactTargetPath: normalizedArtifactPath || undefined,
          writeMode,
        }
      );
    } catch (err) {
      console.error('Project workflow request failed:', err);
      setActiveRunId(null);
      setRunError(err instanceof Error ? err.message : t('projectWorkflow.requestFailed'));
    } finally {
      setRunning(false);
    }
  }, [activeWorkflow, addRecent, artifactPath, currentSessionId, inputValues, loadRecentRuns, projectId, running, t, writeMode]);

  return (
    <div data-name="project-workflows-view" className="flex h-full min-h-0 flex-col overflow-hidden bg-gray-50 px-4 py-4 dark:bg-gray-950">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
        <div className="flex min-w-0 items-start gap-3">
          <div className="rounded-xl bg-amber-50 p-2 text-amber-700 dark:bg-amber-900/30 dark:text-amber-200">
          <BoltIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{t('workspace.workflows.title')}</h2>
            <p className="mt-0.5 text-sm text-gray-600 dark:text-gray-300">
              {t('workspace.workflows.description', { projectName: currentProject?.name || 'project' })}
            </p>
          </div>
        </div>
        {currentProject && (
          <div className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-200">
            {currentProject.name}
          </div>
        )}
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.15fr)_300px]">
        <div className="min-h-0 overflow-y-auto pr-1">
          <ProjectWorkflowPanel
            variant="page"
            projectId={projectId}
            currentFilePath={currentFilePath}
            isRunning={running}
            workflows={projectWorkflows}
            selectedWorkflowId={selectedWorkflowId}
            workflowLoading={workflowsLoading}
            workflowInputs={workflowInputDefs}
            workflowNodeIds={workflowNodeIds}
            inputValues={inputValues}
            artifactPath={artifactPath}
            writeMode={writeMode}
            output={output}
            error={runError || workflowLoadError}
            favorites={favoritesSet}
            recents={recents}
            recommendationContext={recommendationContext}
            onWorkflowChange={handleWorkflowChange}
            onToggleFavorite={toggleFavorite}
            onInputChange={handleInputChange}
            onArtifactPathChange={setArtifactPath}
            onWriteModeChange={setWriteMode}
            onRun={handleRun}
            onStop={handleStop}
            onOpenWorkflows={() => navigate('/workflows')}
          />
        </div>

        <aside className="min-h-0 overflow-hidden">
          <section
            data-name="project-workflows-recent-runs"
            className="flex h-full min-h-[260px] flex-col rounded-2xl border border-gray-200 bg-white/95 p-3 dark:border-gray-800 dark:bg-gray-900/95"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                  {t('workspace.workflows.recentRunsTitle')}
                </h3>
                {recentRuns.length > 0 && (
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500 dark:bg-gray-800 dark:text-gray-300">
                    {recentRuns.length}
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => void loadRecentRuns()}
                className="rounded-lg border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                {t('workspace.workflows.refreshRuns')}
              </button>
            </div>

            <div className="mt-3 min-h-0 flex-1 overflow-y-auto">
              {recentRunsLoading ? (
                <div className="text-sm text-gray-600 dark:text-gray-300">{t('workspace.workflows.recentRunsLoading')}</div>
              ) : recentRunsError ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
                  {recentRunsError}
                </div>
              ) : recentRuns.length === 0 ? (
                <div className="text-sm text-gray-600 dark:text-gray-300">{t('workspace.workflows.recentRunsEmpty')}</div>
              ) : (
                <div className="space-y-2">
                  {recentRuns.map((run) => {
                    const workflowName = run.workflow_id ? workflowNameMap.get(run.workflow_id) : null;
                    const isExpanded = expandedRunId === run.run_id;
                    const hasError = Boolean(run.error?.trim());
                    const statusClass =
                      run.status === 'succeeded'
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                        : run.status === 'running' || run.status === 'queued'
                          ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                          : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300';
                    return (
                      <div
                        key={run.run_id}
                        className="rounded-xl border border-gray-200 bg-gray-50/80 p-3 dark:border-gray-800 dark:bg-gray-950/60"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
                              {workflowName || run.workflow_id || t('workspace.workflows.unknownWorkflow')}
                            </div>
                            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                              <span>{formatRunTime(run.created_at)}</span>
                              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${statusClass}`}>
                                {run.status}
                              </span>
                            </div>
                          </div>
                          {hasError && (
                            <button
                              type="button"
                              onClick={() => setExpandedRunId(isExpanded ? null : run.run_id)}
                              className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-500 hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                              title={run.error || undefined}
                            >
                              {isExpanded ? <ChevronUpIcon className="h-4 w-4" /> : <ChevronDownIcon className="h-4 w-4" />}
                            </button>
                          )}
                        </div>
                        {run.error && (
                          <div
                            className="mt-2 rounded-lg border border-red-200 bg-red-50 px-2.5 py-2 text-xs text-red-600 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300"
                          >
                            {isExpanded ? run.error : truncateRunError(run.error)}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
};
