import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { DocumentIcon } from '@heroicons/react/24/outline';
import { readFile } from '../../../services/api';
import type { Workflow, WorkflowInputDef } from '../../../types/workflow';
import { WorkflowLauncherList } from '../../../shared/workflow-launcher/WorkflowLauncherList';
import type { LauncherRecentItem, LauncherRecommendationContext } from '../../../shared/workflow-launcher/types';
import { useFileSearch } from '../hooks/useFileSearch';

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
  const [pickerQuery, setPickerQuery] = useState('');
  const [pickerError, setPickerError] = useState<string | null>(null);
  const [loadingFieldKey, setLoadingFieldKey] = useState<string | null>(null);
  const { results: fileSearchResults, loading: fileSearchLoading, setQuery: setFileSearchQuery } = useFileSearch(
    projectId,
    currentFilePath
  );
  const canRun = workflows.length > 0 && !workflowLoading;
  const activeFieldLoading = useMemo(
    () => Boolean(loadingFieldKey && pickerFieldKey === loadingFieldKey),
    [loadingFieldKey, pickerFieldKey]
  );

  useEffect(() => {
    setFileSearchQuery(pickerFieldKey ? pickerQuery : '');
  }, [pickerFieldKey, pickerQuery, setFileSearchQuery]);

  useEffect(() => {
    if (!isOpen) {
      setPickerFieldKey(null);
      setPickerQuery('');
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
      setPickerQuery('');
      setPickerError(null);
      setLoadingFieldKey(null);
    }
  }, [pickerFieldKey, workflowInputs]);

  const handleToggleFilePicker = (fieldKey: string) => {
    if (pickerFieldKey === fieldKey) {
      setPickerFieldKey(null);
      setPickerQuery('');
      setPickerError(null);
      return;
    }
    setPickerFieldKey(fieldKey);
    setPickerQuery('');
    setPickerError(null);
  };

  const handleSelectFileForInput = async (fieldKey: string, filePath: string) => {
    if (!projectId) {
      return;
    }
    setLoadingFieldKey(fieldKey);
    setPickerError(null);
    try {
      const fileData = await readFile(projectId, filePath);
      onInputChange(fieldKey, fileData.content);
      setPickerFieldKey(null);
      setPickerQuery('');
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
        <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-2" data-name="project-workflow-inputs">
          <div className="text-xs text-gray-600 dark:text-gray-400 self-start pt-2">
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
                  <label key={field.key} className="block space-y-1" htmlFor={inputName}>
                    <div className="text-xs text-gray-700 dark:text-gray-300">{keyLabel}</div>
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
                  </label>
                );
              }

              if (field.type === 'number') {
                const inputValue = typeof rawValue === 'number' ? String(rawValue) : '';
                return (
                  <label key={field.key} className="block space-y-1" htmlFor={inputName}>
                    <div className="text-xs text-gray-700 dark:text-gray-300">{keyLabel}</div>
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
                  </label>
                );
              }

              const stringValue = typeof rawValue === 'string' ? rawValue : '';
              return (
                <label key={field.key} className="block space-y-1" htmlFor={inputName}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-xs text-gray-700 dark:text-gray-300">{keyLabel}</div>
                    <button
                      type="button"
                      data-name={`project-workflow-insert-file-${field.key}`}
                      disabled={isRunning || activeFieldLoading}
                      onClick={() => handleToggleFilePicker(field.key)}
                      className="px-2 py-1 text-[11px] rounded border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:bg-gray-100 dark:disabled:bg-gray-800/60 disabled:text-gray-400 disabled:cursor-not-allowed"
                    >
                      {loadingFieldKey === field.key
                        ? t('projectWorkflow.loadingFile')
                        : t('projectWorkflow.insertFromFile')}
                    </button>
                  </div>
                  <textarea
                    id={inputName}
                    data-name={inputName}
                    rows={2}
                    value={stringValue}
                    onChange={(event) => onInputChange(field.key, event.target.value)}
                    className="w-full text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  />
                  {pickerFieldKey === field.key && (
                    <div
                      data-name={`project-workflow-file-picker-${field.key}`}
                      className="rounded border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/70 p-2 space-y-2"
                    >
                      <div className="flex gap-2">
                        <input
                          data-name={`project-workflow-file-query-${field.key}`}
                          value={pickerQuery}
                          onChange={(event) => setPickerQuery(event.target.value)}
                          placeholder={t('projectWorkflow.fileSearchPlaceholder')}
                          className="flex-1 text-xs px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
                        />
                        <button
                          type="button"
                          data-name={`project-workflow-file-picker-close-${field.key}`}
                          onClick={() => handleToggleFilePicker(field.key)}
                          className="px-2 py-1 text-[11px] rounded border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                        >
                          {t('common:close')}
                        </button>
                      </div>

                      {pickerError && (
                        <div className="text-xs text-red-700 dark:text-red-300">
                          {pickerError}
                        </div>
                      )}

                      {fileSearchLoading ? (
                        <div className="text-xs text-gray-500 dark:text-gray-400 px-1">
                          {t('projectWorkflow.fileSearchLoading')}
                        </div>
                      ) : fileSearchResults.length === 0 ? (
                        <div className="text-xs text-gray-500 dark:text-gray-400 px-1">
                          {t('projectWorkflow.fileSearchNoResults')}
                        </div>
                      ) : (
                        <div className="max-h-44 overflow-y-auto rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/40">
                          {fileSearchResults.map((result) => (
                            <button
                              key={result.path}
                              type="button"
                              data-name={`project-workflow-file-result-${field.key}-${result.path}`}
                              disabled={activeFieldLoading}
                              onClick={() => void handleSelectFileForInput(field.key, result.path)}
                              className="w-full text-left px-2 py-1.5 border-b border-gray-100 dark:border-gray-700 last:border-b-0 hover:bg-gray-100 dark:hover:bg-gray-700/60 disabled:opacity-60 disabled:cursor-not-allowed"
                            >
                              <div className="flex items-start gap-2">
                                <DocumentIcon className="w-4 h-4 mt-0.5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
                                <div className="min-w-0">
                                  <div className="text-xs font-medium text-gray-800 dark:text-gray-100 truncate">
                                    {result.name}
                                  </div>
                                  <div className="text-[11px] text-gray-500 dark:text-gray-400 truncate">
                                    {result.path}
                                  </div>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </label>
              );
            })}
          </div>
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
    </div>
  );
};
