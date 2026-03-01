import React from 'react';
import { useTranslation } from 'react-i18next';
import type { WorkflowTemplatePreset } from '../templates';

interface WorkflowTemplateGalleryProps {
  templates: WorkflowTemplatePreset[];
  creating: boolean;
  onUseTemplate: (template: WorkflowTemplatePreset) => void;
}

export const WorkflowTemplateGallery: React.FC<WorkflowTemplateGalleryProps> = ({
  templates,
  creating,
  onUseTemplate,
}) => {
  const { t } = useTranslation('workflow');

  return (
    <section
      className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-3"
      data-name="workflow-template-gallery"
    >
      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('templates.title')}</h3>
      <ul className="space-y-2">
        {templates.map((template) => (
          <li
            key={template.id}
            className="rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 p-3"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{t(template.nameKey, template.name)}</div>
                <div className="text-xs text-gray-600 dark:text-gray-300">{t(template.descriptionKey, template.description)}</div>
              </div>
              <button
                type="button"
                onClick={() => onUseTemplate(template)}
                disabled={creating}
                className="shrink-0 rounded-md px-2 py-1 text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-60"
              >
                {t('actions.use')}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
};
