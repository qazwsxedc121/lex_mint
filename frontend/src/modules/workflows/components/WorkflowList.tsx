import React from 'react';
import { useTranslation } from 'react-i18next';
import type { Workflow } from '../../../types/workflow';

interface WorkflowListProps {
  workflows: Workflow[];
  selectedWorkflowId: string | null;
  loading: boolean;
  saving: boolean;
  editable?: boolean;
  onSelect: (workflowId: string) => void;
  onCreate: () => void;
  onDelete: (workflowId: string) => void;
}

export const WorkflowList: React.FC<WorkflowListProps> = ({
  workflows,
  selectedWorkflowId,
  loading,
  saving,
  editable = true,
  onSelect,
  onCreate,
  onDelete,
}) => {
  const { t } = useTranslation('workflow');

  return (
    <section
      className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 flex flex-col gap-3"
      data-name="workflow-list-panel"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('list.title')}</h3>
        {editable && (
          <button
            type="button"
            onClick={onCreate}
            disabled={saving}
            className="rounded-md px-2 py-1 text-xs font-medium bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-60"
          >
            {t('actions.new')}
          </button>
        )}
      </div>

      {loading ? (
        <div className="text-sm text-gray-500 dark:text-gray-400">{t('list.loading')}</div>
      ) : workflows.length === 0 ? (
        <div className="text-sm text-gray-500 dark:text-gray-400">{t('list.empty')}</div>
      ) : (
        <ul className="space-y-2 overflow-y-auto max-h-[56vh]" data-name="workflow-list-items">
          {workflows.map((workflow) => {
            const isActive = workflow.id === selectedWorkflowId;
            return (
              <li key={workflow.id}>
                <div
                  className={`rounded-md border px-3 py-2 cursor-pointer ${
                    isActive
                      ? 'border-blue-400 bg-blue-50 dark:border-blue-600 dark:bg-blue-900/30'
                      : 'border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/40'
                  }`}
                  onClick={() => onSelect(workflow.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      onSelect(workflow.id);
                    }
                  }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">{workflow.name}</span>
                    <div className="flex items-center gap-1">
                      {workflow.is_system && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                          {t('list.system')}
                        </span>
                      )}
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${workflow.enabled ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300'}`}>
                        {workflow.enabled ? t('list.statusOn') : t('list.statusOff')}
                      </span>
                    </div>
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <span className="truncate text-xs text-gray-500 dark:text-gray-400">{workflow.id}</span>
                    {editable && !workflow.is_system && (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onDelete(workflow.id);
                        }}
                        className="text-xs text-red-600 hover:text-red-500 dark:text-red-400 dark:hover:text-red-300"
                      >
                        {t('actions.delete')}
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
};
