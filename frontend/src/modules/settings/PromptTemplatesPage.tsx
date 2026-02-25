/**
 * PromptTemplatesPage - Configuration-driven prompt template management
 */

import React from 'react';
import { QuestionMarkCircleIcon } from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { CrudSettingsPage } from './components/crud';
import { Modal } from './components/common';
import { promptTemplatesConfig } from './config';
import { usePromptTemplates } from './hooks/usePromptTemplates';
import type { CrudHook, CrudSettingsConfig } from './config/types';
import type { PromptTemplate } from '../../types/promptTemplate';

export const PromptTemplatesPage: React.FC = () => {
  const { t } = useTranslation('settings');
  const templatesHook = usePromptTemplates();
  const [showHelpModal, setShowHelpModal] = React.useState(false);

  const crudHook: CrudHook<PromptTemplate> = {
    items: templatesHook.templates,
    loading: templatesHook.loading,
    error: templatesHook.error,
    createItem: templatesHook.createTemplate,
    updateItem: templatesHook.updateTemplate,
    deleteItem: templatesHook.deleteTemplate,
    refreshData: templatesHook.refreshData
  };

  const pageConfig: CrudSettingsConfig<PromptTemplate> = {
    ...promptTemplatesConfig,
    title: (
      <span className="inline-flex items-center gap-2">
        <span>{promptTemplatesConfig.title}</span>
        <button
          type="button"
          onClick={() => setShowHelpModal(true)}
          className="inline-flex items-center justify-center rounded-full text-gray-400 hover:text-blue-600 dark:text-gray-500 dark:hover:text-blue-300 transition-colors"
          title={t('promptTemplates.help.openTitle')}
          data-name="prompt-template-help-trigger"
        >
          <QuestionMarkCircleIcon className="h-4 w-4" />
        </button>
      </span>
    ),
  };

  return (
    <>
      <CrudSettingsPage
        config={pageConfig}
        hook={crudHook}
        context={{}}
        getItemId={(item) => item.id}
      />

      <Modal
        isOpen={showHelpModal}
        onClose={() => setShowHelpModal(false)}
        title={t('promptTemplates.help.title')}
        size="xl"
      >
        <div className="space-y-4 text-sm text-gray-700 dark:text-gray-300 max-h-[70vh] overflow-y-auto pr-1" data-name="prompt-template-help-content">
          <section className="space-y-2">
            <h4 className="text-base font-semibold text-gray-900 dark:text-gray-100">{t('promptTemplates.help.quickStartTitle')}</h4>
            <ul className="list-disc pl-5 space-y-1">
              <li>{t('promptTemplates.help.quickStartItem1')}</li>
              <li>{t('promptTemplates.help.quickStartItem2')}</li>
              <li>{t('promptTemplates.help.quickStartItem3')}</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h4 className="text-base font-semibold text-gray-900 dark:text-gray-100">{t('promptTemplates.help.triggerTitle')}</h4>
            <ul className="list-disc pl-5 space-y-1">
              <li>{t('promptTemplates.help.triggerItem1')}</li>
              <li>{t('promptTemplates.help.triggerItem2')}</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h4 className="text-base font-semibold text-gray-900 dark:text-gray-100">{t('promptTemplates.help.variableTitle')}</h4>
            <p>{t('promptTemplates.help.variableDesc')}</p>
            <pre className="p-3 rounded-md bg-gray-100 dark:bg-gray-900/60 text-xs overflow-x-auto">
{`Write a {{topic}} summary in {{word_count}} words.
Tone: {{style}}
{{cursor}}`}
            </pre>
          </section>
        </div>
      </Modal>
    </>
  );
};
