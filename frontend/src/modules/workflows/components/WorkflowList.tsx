import React from 'react';
import { useTranslation } from 'react-i18next';
import type { Workflow } from '../../../types/workflow';
import { WorkflowLauncherList } from '../../../shared/workflow-launcher/WorkflowLauncherList';
import type { LauncherRecentItem } from '../../../shared/workflow-launcher/types';

interface WorkflowListProps {
  workflows: Workflow[];
  selectedWorkflowId: string | null;
  loading: boolean;
  saving: boolean;
  selectionLocked?: boolean;
  editable?: boolean;
  favorites: Set<string>;
  recents: LauncherRecentItem[];
  onSelect: (workflowId: string) => void;
  onToggleFavorite: (workflowId: string) => void;
  onCreate: () => void;
  onDelete: (workflowId: string) => void;
}

export const WorkflowList: React.FC<WorkflowListProps> = ({
  workflows,
  selectedWorkflowId,
  loading,
  saving,
  selectionLocked = false,
  editable = true,
  favorites,
  recents,
  onSelect,
  onToggleFavorite,
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
            data-name="workflow-list-create"
            onClick={onCreate}
            disabled={saving}
            className="rounded-md px-2 py-1 text-xs font-medium bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-60"
          >
            {t('actions.new')}
          </button>
        )}
      </div>

      <WorkflowLauncherList
        workflows={workflows}
        selectedWorkflowId={selectedWorkflowId}
        loading={loading}
        selectionLocked={selectionLocked}
        namespace="workflow"
        favorites={favorites}
        recents={recents}
        recommendationContext={{ module: 'workflows' }}
        onSelect={onSelect}
        onToggleFavorite={onToggleFavorite}
        emptyMessage={t('list.empty')}
        renderItemActions={(workflow) =>
          editable && !workflow.is_system ? (
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onDelete(workflow.id);
              }}
              className="text-xs text-red-600 hover:text-red-500 dark:text-red-400 dark:hover:text-red-300"
              disabled={saving}
            >
              {t('actions.delete')}
            </button>
          ) : null
        }
      />
    </section>
  );
};
