import React from 'react';
import { useTranslation } from 'react-i18next';
import type { WorkflowScenario } from '../../../types/workflow';

interface WorkflowMetaFormProps {
  name: string;
  description: string;
  enabled: boolean;
  scenario: WorkflowScenario;
  disabled?: boolean;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onEnabledChange: (value: boolean) => void;
  onScenarioChange: (value: WorkflowScenario) => void;
}

export const WorkflowMetaForm: React.FC<WorkflowMetaFormProps> = ({
  name,
  description,
  enabled,
  scenario,
  disabled = false,
  onNameChange,
  onDescriptionChange,
  onEnabledChange,
  onScenarioChange,
}) => {
  const { t } = useTranslation('workflow');

  return (
    <div className="grid grid-cols-1 lg:grid-cols-6 gap-3" data-name="workflow-meta-form">
      <label className="lg:col-span-2 space-y-1">
        <span className="text-xs font-medium text-gray-600 dark:text-gray-300">{t('meta.name')}</span>
        <input
          data-name="workflow-meta-name"
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          disabled={disabled}
          className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
          placeholder={t('meta.namePlaceholder')}
        />
      </label>

      <label className="lg:col-span-2 space-y-1">
        <span className="text-xs font-medium text-gray-600 dark:text-gray-300">{t('meta.description')}</span>
        <input
          data-name="workflow-meta-description"
          value={description}
          onChange={(event) => onDescriptionChange(event.target.value)}
          disabled={disabled}
          className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
          placeholder={t('meta.descriptionPlaceholder')}
        />
      </label>

      <label className="space-y-1">
        <span className="text-xs font-medium text-gray-600 dark:text-gray-300">{t('meta.scenario')}</span>
        <select
          data-name="workflow-meta-scenario"
          value={scenario}
          onChange={(event) => onScenarioChange(event.target.value as WorkflowScenario)}
          disabled={disabled}
          className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          <option value="general">{t('meta.scenarioGeneral')}</option>
          <option value="editor_rewrite">{t('meta.scenarioEditorRewrite')}</option>
        </select>
      </label>

      <label className="space-y-1">
        <span className="text-xs font-medium text-gray-600 dark:text-gray-300">{t('meta.status')}</span>
        <button
          type="button"
          data-name="workflow-meta-status-toggle"
          onClick={() => onEnabledChange(!enabled)}
          disabled={disabled}
          className={`w-full rounded-md border px-3 py-2 text-sm font-medium ${
            enabled
              ? 'border-green-300 bg-green-50 text-green-700 dark:border-green-700 dark:bg-green-900/30 dark:text-green-300'
              : 'border-gray-300 bg-gray-100 text-gray-700 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300'
          } disabled:opacity-60 disabled:cursor-not-allowed`}
        >
          {enabled ? t('meta.enabled') : t('meta.disabled')}
        </button>
      </label>
    </div>
  );
};
