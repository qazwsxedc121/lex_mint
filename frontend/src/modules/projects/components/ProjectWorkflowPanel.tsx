import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FolderOpenIcon } from '@heroicons/react/24/outline';
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
  isOpen: boolean;
  isRunning: boolean;
  workflows: Workflow[];
  selectedWorkflowId: string;
  workflowLoading: boolean;
  workflowInputs: WorkflowInputDef[];
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
  onClose: () => void;
  onOpenWorkflows: () => void;
}

export const ProjectWorkflowPanel: React.FC<ProjectWorkflowPanelProps> = ({
  projectId,
  currentFilePath = null,
  isOpen,
  isRunning,
  workflows,
  selectedWorkflowId,
  workflowLoading,
  workflowInputs,
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
}) => {
  const { t } = useTranslation('projects');
  const [pickerFieldKey, setPickerFieldKey] = useState<string | null>(null);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const [loadingFieldKey, setLoadingFieldKey] = useState<string | null>(null);
  const canRun = workflows.length > 0 && !workflowLoading;
  const activeFieldLoading = useMemo(
    () => Boolean(loadingFieldKey && pickerFieldKey === loadingFieldKey),
    [loadingFieldKey, pickerFieldKey]
  );

  useEffect(() => {
    if (!isOpen) {
      setPickerFieldKey(null);
      setPickerError(null);
      setLoadingFieldKey(null);
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
      setPickerFieldKey(null);
    } catch (error) {
      console.error('Failed to load workflow input file:', error);
      setPickerError(t('projectWorkflow.loadFileFailed'));
    } finally {
      setLoadingFieldKey(null);
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div
      data-name="project-workflow-panel"
      className="border-b border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-3 space-y-3"
    >
      <div className="space-y-2">
        <WorkflowLauncherList
          workflows={workflows}
          selectedWorkflowId={selectedWorkflowId || null}
          loading={workflowLoading}
          selectionLocked={isRunning}
          namespace="projects"
          compact
          showSearch
          maxWidthClassName="max-w-full xl:max-w-[920px]"
          headerActions={(
            <button
              type="button"
              onClick={onClose}
              className="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              {t('common:close')}
            </button>
          )}
          favorites={favorites}
          recents={recents}
          recommendationContext={recommendationContext}
          onSelect={onWorkflowChange}
          onToggleFavorite={onToggleFavorite}
          emptyMessage={t('projectWorkflow.noWorkflows')}
        />

        {!workflowLoading && workflows.length === 0 && (
          <div className="rounded-md border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/60 p-3">
            <div className="text-xs text-gray-600 dark:text-gray-300">{t('projectWorkflow.emptyHint')}</div>
            <button
              type="button"
              onClick={onOpenWorkflows}
              className="mt-2 px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white"
            >
              {t('workflowLauncher.openWorkflows')}
            </button>
          </div>
        )}
      </div>

      {workflowInputs.length > 0 && (
        <div
          data-name="project-workflow-inputs"
          className="relative rounded border border-gray-300 dark:border-gray-700 bg-gray-50/70 dark:bg-gray-800/30 px-3 pb-3 pt-4"
        >
          <div className="absolute -top-2 left-3 px-1 text-xs text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-900">
            {t('projectWorkflow.workflowInputsLabel')}
          </div>
          <div className="space-y-2">
            {workflowInputs.map((field) => {
              const rawValue = inputValues[field.key];
              const keyLabel = field.required
                ? `${field.key} (${t('projectWorkflow.required')})`
                : field.key;
              const inputName = `project-workflow-input-${field.key}`;

              if (field.type === 'boolean') {
                const selectValue = rawValue === true ? 'true' : rawValue === false ? 'false' : '';
                return (
                  <div key={field.key} className="grid grid-cols-1 lg:grid-cols-[180px_minmax(0,1fr)] items-center gap-2">
                    <label htmlFor={inputName} className="text-xs text-gray-700 dark:text-gray-300">
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
                      className="w-full text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    >
                      <option value="">{t('projectWorkflow.booleanUnset')}</option>
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  </div>
                );
              }

              if (field.type === 'number') {
                const inputValue = typeof rawValue === 'number' ? String(rawValue) : '';
                return (
                  <div key={field.key} className="grid grid-cols-1 lg:grid-cols-[180px_minmax(0,1fr)] items-center gap-2">
                    <label htmlFor={inputName} className="text-xs text-gray-700 dark:text-gray-300">
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
                      className="w-full text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                );
              }

              const stringValue = typeof rawValue === 'string' ? rawValue : '';
              const canInsertFromFile = canInsertFileForInput(field);
              return (
                <div key={field.key} className="grid grid-cols-1 lg:grid-cols-[180px_minmax(0,1fr)_auto] items-start gap-2">
                  <label htmlFor={inputName} className="text-xs text-gray-700 dark:text-gray-300 lg:pt-1.5">
                    {keyLabel}
                  </label>
                  <textarea
                    id={inputName}
                    data-name={inputName}
                    rows={2}
                    value={stringValue}
                    onChange={(event) => onInputChange(field.key, event.target.value)}
                    className="w-full min-w-0 text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  />
                  {canInsertFromFile ? (
                    <div className="flex shrink-0 items-start gap-1 lg:pt-0.5">
                      <button
                        type="button"
                        data-name={`project-workflow-insert-file-${field.key}`}
                        disabled={isRunning || activeFieldLoading}
                        onClick={() => handleToggleFilePicker(field.key)}
                        title={loadingFieldKey === field.key ? t('projectWorkflow.loadingFile') : t('projectWorkflow.insertFromFile')}
                        className="inline-flex h-7 w-7 items-center justify-center rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:bg-gray-100 dark:disabled:bg-gray-800/60 disabled:text-gray-400 disabled:cursor-not-allowed"
                      >
                        <FolderOpenIcon className="h-4 w-4" />
                      </button>
                    </div>
                  ) : (
                    <div className="hidden lg:block" />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {pickerError && (
        <div className="text-xs text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded px-2 py-1.5">
          {pickerError}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2" data-name="project-workflow-artifact-settings">
        <label className="block space-y-1">
          <div className="text-xs text-gray-700 dark:text-gray-300">{t('projectWorkflow.artifactPath')}</div>
          <input
            data-name="project-workflow-artifact-path"
            value={artifactPath}
            onChange={(event) => onArtifactPathChange(event.target.value)}
            placeholder={t('projectWorkflow.artifactPathPlaceholder')}
            className="w-full text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          />
        </label>
        <label className="block space-y-1">
          <div className="text-xs text-gray-700 dark:text-gray-300">{t('projectWorkflow.writeMode')}</div>
          <select
            data-name="project-workflow-write-mode"
            value={writeMode}
            onChange={(event) => onWriteModeChange(event.target.value as 'none' | 'create' | 'overwrite')}
            className="w-full text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          >
            <option value="overwrite">{t('projectWorkflow.writeModeOverwrite')}</option>
            <option value="create">{t('projectWorkflow.writeModeCreate')}</option>
            <option value="none">{t('projectWorkflow.writeModeNone')}</option>
          </select>
        </label>
      </div>

      {error && (
        <div className="text-xs text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded px-2 py-1.5">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {!isRunning ? (
          <button
            type="button"
            data-name="project-workflow-run"
            onClick={onRun}
            disabled={!canRun}
            className="px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed"
          >
            {t('projectWorkflow.run')}
          </button>
        ) : (
          <button
            type="button"
            data-name="project-workflow-stop"
            onClick={onStop}
            className="px-3 py-1.5 rounded text-xs font-medium border border-amber-500 text-amber-700 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/20"
          >
            {t('projectWorkflow.stop')}
          </button>
        )}
      </div>

      <div className="space-y-1">
        <div className="text-xs font-medium text-gray-700 dark:text-gray-300">
          {t('projectWorkflow.output')}
        </div>
        <pre
          data-name="project-workflow-output"
          className="text-xs max-h-56 overflow-auto rounded border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-2 whitespace-pre-wrap break-words"
        >
          {output || (isRunning ? t('projectWorkflow.running') : t('projectWorkflow.emptyOutput'))}
        </pre>
      </div>

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
