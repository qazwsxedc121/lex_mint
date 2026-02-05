/**
 * ModelsPage - Configuration-driven model management
 *
 * This page is now powered by the modelsConfig, reducing boilerplate
 * from 424 lines (ModelList.tsx) to just ~35 lines.
 */

import React from 'react';
import { CrudSettingsPage } from './components/crud';
import { modelsConfig } from './config';
import { useModels } from './hooks/useModels';
import type { CrudHook } from './config/types';
import type { Model } from '../../types/model';

export const ModelsPage: React.FC = () => {
  const modelsHook = useModels();

  // Adapt useModels hook to CrudHook interface
  const crudHook: CrudHook<Model> = {
    items: modelsHook.models,
    loading: modelsHook.loading,
    error: modelsHook.error,
    createItem: modelsHook.createModel,
    updateItem: (id, data) => {
      // Models use composite key provider_id:id
      return modelsHook.updateModel(id, data as Model);
    },
    deleteItem: modelsHook.deleteModel,
    refreshData: modelsHook.refreshData
  };

  return (
    <CrudSettingsPage
      config={modelsConfig}
      hook={crudHook}
      context={{ providers: modelsHook.providers }}
      getItemId={(item) => `${item.provider_id}:${item.id}`}
    />
  );
};
