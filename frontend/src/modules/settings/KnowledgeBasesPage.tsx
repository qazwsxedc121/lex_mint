/**
 * KnowledgeBasesPage - Configuration-driven knowledge base management
 */

import React from 'react';
import { CrudSettingsPage } from './components/crud';
import { knowledgeBasesConfig } from './config';
import { useKnowledgeBases } from './hooks/useKnowledgeBases';
import type { CrudHook } from './config/types';
import type { KnowledgeBase } from '../../types/knowledgeBase';

export const KnowledgeBasesPage: React.FC = () => {
  const kbHook = useKnowledgeBases();

  // Adapt useKnowledgeBases hook to CrudHook interface
  const crudHook: CrudHook<KnowledgeBase> = {
    items: kbHook.knowledgeBases,
    loading: kbHook.loading,
    error: kbHook.error,
    createItem: kbHook.createKnowledgeBase,
    updateItem: kbHook.updateKnowledgeBase,
    deleteItem: kbHook.deleteKnowledgeBase,
    refreshData: kbHook.refreshData
  };

  return (
    <CrudSettingsPage
      config={knowledgeBasesConfig}
      hook={crudHook}
      context={{}}
      getItemId={(item) => item.id}
    />
  );
};
