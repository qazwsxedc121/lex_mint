/**
 * AssistantsPage - Configuration-driven assistant management
 *
 * This page is now powered by the assistantsConfig, reducing boilerplate
 * from 357 lines (AssistantList.tsx) to just ~40 lines.
 */

import React from 'react';
import { CrudSettingsPage } from './components/crud';
import { assistantsConfig } from './config';
import { useModels } from './hooks/useModels';
import { useAssistants } from './hooks/useAssistants';
import type { CrudHook } from './config/types';
import type { Assistant } from '../../types/assistant';

export const AssistantsPage: React.FC = () => {
  const modelsHook = useModels();
  const assistantsHook = useAssistants();

  // Adapt useAssistants hook to CrudHook interface
  const crudHook: CrudHook<Assistant> = {
    items: assistantsHook.assistants,
    defaultItemId: assistantsHook.defaultAssistantId,
    loading: assistantsHook.loading || modelsHook.loading,
    error: assistantsHook.error || modelsHook.error,
    createItem: assistantsHook.createAssistant,
    updateItem: assistantsHook.updateAssistant,
    deleteItem: assistantsHook.deleteAssistant,
    setDefault: assistantsHook.setDefaultAssistant,
    refreshData: assistantsHook.refreshData
  };

  return (
    <CrudSettingsPage
      config={assistantsConfig}
      hook={crudHook}
      context={{ models: modelsHook.models, providers: modelsHook.providers }}
      getItemId={(item) => item.id}
    />
  );
};
