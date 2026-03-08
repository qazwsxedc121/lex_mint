import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDownIcon, ChevronUpIcon, DocumentIcon, FolderOpenIcon, SparklesIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { readFile } from '../../../services/api';
import type { Workflow, WorkflowInputDef } from '../../../types/workflow';
import { WorkflowLauncherList } from '../../../shared/workflow-launcher/WorkflowLauncherList';
import type { LauncherRecentItem, LauncherRecommendationContext } from '../../../shared/workflow-launcher/types';
import { FilePickerDialog } from './FilePickerDialog';

const isIdentifierLikeField = (fieldKey: string): boolean => {
  const normalized = fieldKey.trim().toLowerCase();
  return normalized === 'id' || normalized.endsWith('_id');
};

const canInsertFileForInput = (field: WorkflowInputDef): boolean => {
  if (field.type !== 'string') {
    return false;
  }
  if (typeof field.allow_file_insert === 'boolean') {
    return field.allow_file_insert;
  }
  // Backward-compatible safety for old schemas without explicit allow_file_insert.
  return !isIdentifierLikeField(field.key);
};

interface ProjectWorkflowPanelProps {
  projectId: string;
  currentFilePath?: string | null;
  isOpen?: boolean;
  variant?: 'inline' | 'page';
  isRunning: boolean;
  workflows: Workflow[];
  selectedWorkflowId: string;
  workflowLoading: boolean;
  workflowInputs: WorkflowInputDef[];
  workflowNodeIds?: string[];
  inputValues: Record<string, unknown>;
  artifactPath: string;
  writeMode: 'none' | 'create' | 'overwrite';
  output: string;
  error: string | null;
  favorites: Set<string>;
  recents: LauncherRecentItem[];
  recommendationContext: LauncherRecommendationContext;
  onWorkflowChange: (workflowId: string) => void;
  onToggleFavorite: (workflowId: string) => void;
  onInputChange: (key: string, value: unknown) => void;
  onArtifactPathChange: (path: string) => void;
  onWriteModeChange: (mode: 'none' | 'create' | 'overwrite') => void;
  onRun: () => void;
  onStop: () => void;
  onClose?: () => void;
  onOpenWorkflows: () => void;
  onSendOutputToAgent?: () => void;
  sendOutputToAgentDisabled?: boolean;
  sendOutputToAgentTitle?: string;
}

interface FileBackedInputMeta {
  path: string;
}

export const ProjectWorkflowPanel: React.FC<ProjectWorkflowPanelProps> = ({
  projectId,
  currentFilePath = null,
  isOpen = true,
  variant = 'inline',
  isRunning,
  workflows,
  selectedWorkflowId,
  workflowLoading,
  workflowInputs,
  workflowNodeIds = [],
  inputValues,
  artifactPath,
  writeMode,
  output,
  error,
  favorites,
  recents,
  recommendationContext,
  onWorkflowChange,
  onToggleFavorite,
  onInputChange,
  onArtifactPathChange,
  onWriteModeChange,
  onRun,
  onStop,
  onClose,
  onOpenWorkflows,
  onSendOutputToAgent,
  sendOutputToAgentDisabled = false,
  sendOutputToAgentTitle,
}) => {
  const { t, i18n } = useTranslation('projects');
  const [pickerFieldKey, setPickerFieldKey] = useState<string | null>(null);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const [loadingFieldKey, setLoadingFieldKey] = useState<string | null>(null);
  const [fileBackedInputs, setFileBackedInputs] = useState<Record<string, FileBackedInputMeta>>({});
  const [workflowChooserCollapsed, setWorkflowChooserCollapsed] = useState(false);

  const canRun = workflows.length > 0 && !workflowLoading;
  const activeWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.id === selectedWorkflowId) || workflows[0] || null,
    [selectedWorkflowId, workflows]
  );
  const requiredInputCount = useMemo(
    () => workflowInputs.filter((field) => field.required).length,
    [workflowInputs]
  );
  const activeFieldLoading = useMemo(
    () => Boolean(loadingFieldKey && pickerFieldKey === loadingFieldKey),
    [loadingFieldKey, pickerFieldKey]
  );

  useEffect(() => {
    if (!isOpen) {
      setPickerFieldKey(null);
      setPickerError(null);
      setLoadingFieldKey(null);
      setFileBackedInputs({});
    }
  }, [isOpen]);

  useEffect(() => {
    if (!pickerFieldKey) {
      return;
    }
    if (!workflowInputs.some((field) => field.key === pickerFieldKey)) {
      setPickerFieldKey(null);
      setPickerError(null);
      setLoadingFieldKey(null);
    }
  }, [pickerFieldKey, workflowInputs]);

  useEffect(() => {
    const validKeys = new Set(workflowInputs.map((field) => field.key));
    setFileBackedInputs((previous) => {
      let changed = false;
      const next: Record<string, FileBackedInputMeta> = {};
      Object.entries(previous).forEach(([key, metadata]) => {
        if (validKeys.has(key)) {
          next[key] = metadata;
        } else {
          changed = true;
        }
      });
      return changed ? next : previous;
    });
  }, [workflowInputs]);

  useEffect(() => {
    if (!activeWorkflow) {
      setWorkflowChooserCollapsed(false);
    }
  }, [activeWorkflow]);

  const handleToggleFilePicker = (fieldKey: string) => {
    if (pickerFieldKey === fieldKey) {
      setPickerFieldKey(null);
      setPickerError(null);
      return;
    }
    setPickerFieldKey(fieldKey);
    setPickerError(null);
  };

  const handleSelectFileForInput = async (filePath: string) => {
    if (!projectId || !pickerFieldKey) {
      return;
    }
    const targetFieldKey = pickerFieldKey;
    setLoadingFieldKey(targetFieldKey);
    setPickerError(null);
    try {
      const fileData = await readFile(projectId, filePath);
      onInputChange(targetFieldKey, fileData.content);
      setFileBackedInputs((previous) => ({
        ...previous,
        [targetFieldKey]: {
          path: filePath,
        },
      }));
      setPickerFieldKey(null);
    } catch (loadError) {
      console.error('Failed to load workflow input file:', loadError);
      setPickerError(t('projectWorkflow.loadFileFailed'));
    } finally {
      setLoadingFieldKey(null);
    }
  };

  const handleWorkflowSelect = (workflowId: string) => {
    onWorkflowChange(workflowId);
    if (variant === 'page') {
      setWorkflowChooserCollapsed(true);
    }
  };

  if (!isOpen) {
    return null;
  }

  const showCloseButton = variant === 'inline' && typeof onClose === 'function';
  const isZhLocale = i18n.resolvedLanguage?.toLowerCase().startsWith('zh') ?? false;
  const inputsLabel = isZhLocale ? '输入项' : 'Inputs';
  const requiredLabel = isZhLocale ? '必填项' : 'Required';
  const nodesLabel = isZhLocale ? '节点数' : 'Nodes';
  const fieldLabel = isZhLocale ? '字段' : 'Field';
  const valueLabel = isZhLocale ? '值' : 'Value';
  const toolsLabel = isZhLocale ? '工具' : 'Tools';

  const fieldShellClassName =
    'grid items-start gap-3 rounded-xl border border-gray-200 bg-gray-50/70 p-3 dark:border-gray-800 dark:bg-gray-900/60 lg:grid-cols-[160px_minmax(0,1fr)_auto]';
  const fieldLabelClassName = 'text-xs font-medium text-gray-700 dark:text-gray-300 lg:pt-2';
  const controlClassName =
    'w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100';

  const renderInputField = (field: WorkflowInputDef): React.ReactNode => {
    const rawValue = inputValues[field.key];
    const keyLabel = field.required ? `${field.key} (${t('projectWorkflow.required')})` : field.key;
    const inputName = `project-workflow-input-${field.key}`;
    const fileBackedMeta = fileBackedInputs[field.key];

    if (field.type === 'boolean') {
      const selectValue = rawValue === true ? 'true' : rawValue === false ? 'false' : '';
      return (
        <div key={field.key} className={fieldShellClassName}>
          <label htmlFor={inputName} className={fieldLabelClassName}>
            {keyLabel}
          </label>
          <select
            id={inputName}
            data-name={inputName}
            value={selectValue}
            onChange={(event) => {
              const value = event.target.value;
              if (!value) {
                onInputChange(field.key, undefined);
                return;
              }
              onInputChange(field.key, value === 'true');
            }}
            className={controlClassName}
          >
            <option value="">{t('projectWorkflow.booleanUnset')}</option>
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
          <div className="hidden lg:block" />
        </div>
      );
    }

    if (field.type === 'number') {
      const inputValue = typeof rawValue === 'number' ? String(rawValue) : '';
      return (
        <div key={field.key} className={fieldShellClassName}>
          <label htmlFor={inputName} className={fieldLabelClassName}>
            {keyLabel}
          </label>
          <input
            id={inputName}
            data-name={inputName}
            type="number"
            value={inputValue}
            onChange={(event) => {
              const value = event.target.value;
              if (!value.trim()) {
                onInputChange(field.key, undefined);
                return;
              }
              onInputChange(field.key, Number(value));
            }}
            className={controlClassName}
          />
          <div className="hidden lg:block" />
        </div>
      );
    }

    if (field.type === 'node') {
      const selectValue = typeof rawValue === 'string' ? rawValue : '';
      return (
        <div key={field.key} className={fieldShellClassName}>
          <label htmlFor={inputName} className={fieldLabelClassName}>
            {keyLabel}
          </label>
          <select
            id={inputName}
            data-name={inputName}
            value={selectValue}
            onChange={(event) => {
              const value = event.target.value;
              onInputChange(field.key, value || undefined);
            }}
            className={controlClassName}
          >
            <option value="">{t('workflow:nodeEditor.selectNodePlaceholder')}</option>
            {workflowNodeIds.map((nodeId) => (
              <option key={`project-workflow-node-input-${field.key}-${nodeId}`} value={nodeId}>
                {nodeId}
              </option>
            ))}
          </select>
          <div className="hidden lg:block" />
        </div>
      );
    }

    const stringValue = typeof rawValue === 'string' ? rawValue : '';
    const canInsertFromFile = canInsertFileForInput(field);

    return (
      <div key={field.key} className={fieldShellClassName}>
        <label htmlFor={inputName} className={fieldLabelClassName}>
          {keyLabel}
        </label>
        {fileBackedMeta ? (
          <div className="w-full min-w-0 rounded-xl border border-blue-200 bg-blue-50/80 px-3 py-2 dark:border-blue-800 dark:bg-blue-900/20">
            <div className="flex min-w-0 items-start gap-2">
              <DocumentIcon className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-600 dark:text-blue-300" />
              <div className="min-w-0 flex-1">
                <div className="text-xs font-medium text-blue-800 dark:text-blue-200">
                  {t('projectWorkflow.insertFromFile')}
                </div>
                <div className="truncate text-[11px] text-blue-700/90 dark:text-blue-300">
                  {fileBackedMeta.path}
                </div>
              </div>
              <button
                type="button"
                data-name={`project-workflow-file-widget-clear-${field.key}`}
                onClick={() => {
                  setFileBackedInputs((previous) => {
                    if (!previous[field.key]) {
                      return previous;
                    }
                    const next = { ...previous };
                    delete next[field.key];
                    return next;
                  });
                }}
                className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-blue-200 bg-white/90 text-blue-700 hover:bg-white dark:border-blue-700 dark:bg-gray-800 dark:text-blue-300 dark:hover:bg-gray-700"
                title={t('common:close')}
              >
                <XMarkIcon className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ) : (
          <textarea
            id={inputName}
            data-name={inputName}
            rows={3}
            value={stringValue}
            onChange={(event) => {
              onInputChange(field.key, event.target.value);
              if (fileBackedInputs[field.key]) {
                setFileBackedInputs((previous) => {
                  const next = { ...previous };
                  delete next[field.key];
                  return next;
                });
              }
            }}
            className={controlClassName}
          />
        )}
        {canInsertFromFile ? (
          <div className="flex shrink-0 items-start gap-1 lg:pt-1">
            <button
              type="button"
              data-name={`project-workflow-insert-file-${field.key}`}
              disabled={isRunning || activeFieldLoading}
              onClick={() => handleToggleFilePicker(field.key)}
              title={loadingFieldKey === field.key ? t('projectWorkflow.loadingFile') : t('projectWorkflow.insertFromFile')}
              className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-gray-300 bg-white text-gray-600 hover:bg-gray-100 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700 dark:disabled:bg-gray-800/60"
            >
              <FolderOpenIcon className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <div className="hidden lg:block" />
        )}
      </div>
    );
  };

  return (
    <div
      data-name="project-workflow-panel"
      className={
        variant === 'page'
          ? 'space-y-4 rounded-[24px] border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900'
          : 'space-y-3 border-b border-gray-300 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-900'
      }
    >
      {activeWorkflow && workflowChooserCollapsed ? (
        <section className="rounded-2xl border border-blue-200 bg-gradient-to-r from-blue-50 via-white to-slate-50 p-4 dark:border-blue-900/60 dark:from-blue-950/40 dark:via-gray-900 dark:to-gray-900">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-blue-700 dark:text-blue-300">
                <SparklesIcon className="h-4 w-4" />
                {t('projectWorkflow.title')}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <h3 className="truncate text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {activeWorkflow.name}
                </h3>
                <span className="rounded-full border border-blue-200 bg-white/80 px-2.5 py-1 text-[11px] font-medium text-blue-700 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200">
                  {activeWorkflow.id}
                </span>
                {activeWorkflow.is_system && (
                  <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                    {t('workflowLauncher.badge.system')}
                  </span>
                )}
                <span
                  className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                    activeWorkflow.enabled
                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                      : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                  }`}
                >
                  {activeWorkflow.enabled
                    ? t('workflowLauncher.badge.enabled')
                    : t('workflowLauncher.badge.disabled')}
                </span>
              </div>
              {activeWorkflow.description && (
                <p className="mt-2 truncate text-sm text-gray-600 dark:text-gray-300">
                  {activeWorkflow.description}
                </p>
              )}
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                <span className="rounded-full bg-white/80 px-2.5 py-1 dark:bg-gray-900/70">{inputsLabel}: {workflowInputs.length}</span>
                <span className="rounded-full bg-white/80 px-2.5 py-1 dark:bg-gray-900/70">{requiredLabel}: {requiredInputCount}</span>
                <span className="rounded-full bg-white/80 px-2.5 py-1 dark:bg-gray-900/70">{nodesLabel}: {activeWorkflow.nodes.length}</span>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setWorkflowChooserCollapsed(false)}
              className="inline-flex items-center gap-2 rounded-xl border border-blue-200 bg-white/80 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-white dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-200 dark:hover:bg-blue-950/50"
            >
              <ChevronDownIcon className="h-4 w-4" />
              {t('common:expand', { defaultValue: 'Expand' })}
            </button>
          </div>
        </section>
      ) : (
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.75fr)_360px] xl:items-start">
        <section className="w-full min-w-0 space-y-3 rounded-2xl border border-gray-200 bg-gray-50/80 p-3 dark:border-gray-800 dark:bg-gray-950/40">
          <WorkflowLauncherList
            workflows={workflows}
            selectedWorkflowId={selectedWorkflowId || null}
            loading={workflowLoading}
            selectionLocked={isRunning}
            namespace="projects"
            compact={variant !== 'page'}
            showSearch
            maxWidthClassName="w-full max-w-full"
            headerActions={showCloseButton ? (
              <button
                type="button"
                onClick={onClose}
                className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                {t('common:close')}
              </button>
            ) : undefined}
            favorites={favorites}
            recents={recents}
            recommendationContext={recommendationContext}
            onSelect={handleWorkflowSelect}
            onToggleFavorite={onToggleFavorite}
            emptyMessage={t('projectWorkflow.noWorkflows')}
            itemLayout="dense"
          />

          {!workflowLoading && workflows.length === 0 && (
            <div className="rounded-xl border border-gray-300 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800/60">
              <div className="text-xs text-gray-600 dark:text-gray-300">{t('projectWorkflow.emptyHint')}</div>
              <button
                type="button"
                onClick={onOpenWorkflows}
                className="mt-2 rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
              >
                {t('workflowLauncher.openWorkflows')}
              </button>
            </div>
          )}
        </section>

        {activeWorkflow ? (
          <section className="rounded-2xl border border-blue-200 bg-gradient-to-b from-blue-50 via-white to-slate-50 p-4 dark:border-blue-900/60 dark:from-blue-950/40 dark:via-gray-900 dark:to-gray-900 xl:sticky xl:top-0">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-blue-700 dark:text-blue-300">
                  <SparklesIcon className="h-4 w-4" />
                  {t('projectWorkflow.title')}
                </div>
                <h3 className="mt-2 text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {activeWorkflow.name}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setWorkflowChooserCollapsed(true)}
                className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-white/80 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-white dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-200 dark:hover:bg-blue-950/50"
              >
                <ChevronUpIcon className="h-4 w-4" />
                {t('common:collapse', { defaultValue: 'Collapse' })}
              </button>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-blue-200 bg-white/80 px-2.5 py-1 text-[11px] font-medium text-blue-700 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200">
                {activeWorkflow.id}
              </span>
              {activeWorkflow.is_system && (
                <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                  {t('workflowLauncher.badge.system')}
                </span>
              )}
              <span
                className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                  activeWorkflow.enabled
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                    : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                }`}
              >
                {activeWorkflow.enabled
                  ? t('workflowLauncher.badge.enabled')
                  : t('workflowLauncher.badge.disabled')}
              </span>
            </div>

            {activeWorkflow.description && (
              <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">
                {activeWorkflow.description}
              </p>
            )}

            <div className="mt-4 grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
              <div className="rounded-xl border border-white/80 bg-white/80 px-3 py-2 dark:border-gray-800 dark:bg-gray-900/80">
                <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400">{inputsLabel}</div>
                <div className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">{workflowInputs.length}</div>
              </div>
              <div className="rounded-xl border border-white/80 bg-white/80 px-3 py-2 dark:border-gray-800 dark:bg-gray-900/80">
                <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400">{requiredLabel}</div>
                <div className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">{requiredInputCount}</div>
              </div>
              <div className="rounded-xl border border-white/80 bg-white/80 px-3 py-2 dark:border-gray-800 dark:bg-gray-900/80">
                <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400">{nodesLabel}</div>
                <div className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">{activeWorkflow.nodes.length}</div>
              </div>
            </div>
          </section>
        ) : (
          <section className="rounded-2xl border border-gray-200 bg-gray-50/80 p-4 text-sm text-gray-500 dark:border-gray-800 dark:bg-gray-950/40 dark:text-gray-400">
            {t('projectWorkflow.noWorkflows')}
          </section>
        )}
      </div>
      )}

      {workflowInputs.length > 0 && (
        <section
          data-name="project-workflow-inputs"
          className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950/30"
        >
          <div className="mb-4 flex items-center justify-between gap-3 border-b border-gray-200 pb-3 dark:border-gray-800">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-gray-400">
              {t('projectWorkflow.workflowInputsLabel')}
            </div>
            <div className="text-[11px] text-gray-500 dark:text-gray-400">{workflowInputs.length}</div>
          </div>

          <div className="space-y-3">
            <div className="hidden text-[11px] uppercase tracking-wide text-gray-400 dark:text-gray-500 lg:grid lg:grid-cols-[160px_minmax(0,1fr)_auto] lg:gap-3 lg:px-1">
              <div>{fieldLabel}</div>
              <div>{valueLabel}</div>
              <div>{toolsLabel}</div>
            </div>
            <div className="space-y-3">{workflowInputs.map((field) => renderInputField(field))}</div>
          </div>
        </section>
      )}

      <section className="rounded-2xl border border-gray-200 bg-gray-50/80 p-4 dark:border-gray-800 dark:bg-gray-950/40">
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_220px_auto] xl:items-end" data-name="project-workflow-artifact-settings">
          <label className="block space-y-1">
            <div className="text-xs font-medium text-gray-700 dark:text-gray-300">{t('projectWorkflow.artifactPath')}</div>
            <input
              data-name="project-workflow-artifact-path"
              value={artifactPath}
              onChange={(event) => onArtifactPathChange(event.target.value)}
              placeholder={t('projectWorkflow.artifactPathPlaceholder')}
              className={controlClassName}
            />
          </label>

          <label className="block space-y-1">
            <div className="text-xs font-medium text-gray-700 dark:text-gray-300">{t('projectWorkflow.writeMode')}</div>
            <select
              data-name="project-workflow-write-mode"
              value={writeMode}
              onChange={(event) => onWriteModeChange(event.target.value as 'none' | 'create' | 'overwrite')}
              className={controlClassName}
            >
              <option value="overwrite">{t('projectWorkflow.writeModeOverwrite')}</option>
              <option value="create">{t('projectWorkflow.writeModeCreate')}</option>
              <option value="none">{t('projectWorkflow.writeModeNone')}</option>
            </select>
          </label>

          <div className="flex flex-wrap gap-2 xl:justify-end">
            {!isRunning ? (
              <button
                type="button"
                data-name="project-workflow-run"
                onClick={onRun}
                disabled={!canRun}
                className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300 disabled:text-gray-500 dark:disabled:bg-gray-700"
              >
                {t('projectWorkflow.run')}
              </button>
            ) : (
              <button
                type="button"
                data-name="project-workflow-stop"
                onClick={onStop}
                className="rounded-xl border border-amber-500 px-4 py-2.5 text-sm font-medium text-amber-700 hover:bg-amber-50 dark:text-amber-300 dark:hover:bg-amber-900/20"
              >
                {t('projectWorkflow.stop')}
              </button>
            )}
          </div>
        </div>

        {(pickerError || error) && (
          <div className="mt-3 space-y-2">
            {pickerError && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
                {pickerError}
              </div>
            )}
            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
                {error}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950/30">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-gray-400">
            {t('projectWorkflow.output')}
          </div>
          <div className="flex items-center gap-2">
            {onSendOutputToAgent && (
              <button
                type="button"
                onClick={onSendOutputToAgent}
                disabled={sendOutputToAgentDisabled}
                title={sendOutputToAgentTitle}
                data-name="project-workflow-send-output-to-agent"
                className="rounded-lg border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                {t('workspace.agent.sendToAgent')}
              </button>
            )}
            {isRunning && (
              <span className="rounded-full bg-blue-100 px-2.5 py-1 text-[11px] font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                {t('projectWorkflow.running')}
              </span>
            )}
          </div>
        </div>

        {output ? (
          <pre
            data-name="project-workflow-output"
            className="max-h-64 overflow-auto rounded-xl border border-gray-200 bg-gray-50 p-3 text-xs whitespace-pre-wrap break-words dark:border-gray-800 dark:bg-gray-900/80"
          >
            {output}
          </pre>
        ) : (
          <div
            data-name="project-workflow-output"
            className="rounded-xl border border-dashed border-gray-300 bg-gray-50 px-3 py-4 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-900/60 dark:text-gray-400"
          >
            {isRunning ? t('projectWorkflow.running') : t('projectWorkflow.emptyOutput')}
          </div>
        )}
      </section>

      <FilePickerDialog
        projectId={projectId}
        isOpen={Boolean(pickerFieldKey)}
        title={pickerFieldKey ? `${t('projectWorkflow.insertFromFile')} (${pickerFieldKey})` : t('projectWorkflow.insertFromFile')}
        selectedPath={currentFilePath}
        onClose={() => setPickerFieldKey(null)}
        onSelect={(filePath) => {
          void handleSelectFileForInput(filePath);
        }}
      />
    </div>
  );
};
