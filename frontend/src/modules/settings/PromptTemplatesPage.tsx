/**
 * PromptTemplatesPage - Configuration-driven prompt template management
 */

import React from 'react';
import { CrudSettingsPage } from './components/crud';
import { promptTemplatesConfig } from './config';
import { usePromptTemplates } from './hooks/usePromptTemplates';
import type { CrudHook } from './config/types';
import type { PromptTemplate } from '../../types/promptTemplate';

export const PromptTemplatesPage: React.FC = () => {
  const templatesHook = usePromptTemplates();

  const crudHook: CrudHook<PromptTemplate> = {
    items: templatesHook.templates,
    loading: templatesHook.loading,
    error: templatesHook.error,
    createItem: templatesHook.createTemplate,
    updateItem: templatesHook.updateTemplate,
    deleteItem: templatesHook.deleteTemplate,
    refreshData: templatesHook.refreshData
  };

  return (
    <CrudSettingsPage
      config={promptTemplatesConfig}
      hook={crudHook}
      context={{}}
      getItemId={(item) => item.id}
    />
  );
};
