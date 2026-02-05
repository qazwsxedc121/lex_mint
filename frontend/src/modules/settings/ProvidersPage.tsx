/**
 * ProvidersPage - Configuration-driven provider management
 *
 * This page is now powered by the providersConfig, reducing boilerplate
 * from 660 lines (ProviderList.tsx) to just ~30 lines.
 *
 * Note: Advanced features like builtin provider picker and test connection
 * are not yet included in this refactored version. They can be added back
 * as custom actions in the config.
 */

import React from 'react';
import { CrudSettingsPage } from './components/crud';
import { providersConfig } from './config';
import { useModels } from './hooks/useModels';
import type { CrudHook } from './config/types';
import type { Provider } from '../../types/model';

export const ProvidersPage: React.FC = () => {
  const modelsHook = useModels();

  // Adapt useModels hook to CrudHook interface for providers
  const crudHook: CrudHook<Provider> = {
    items: modelsHook.providers,
    loading: modelsHook.loading,
    error: modelsHook.error,
    createItem: modelsHook.createProvider,
    updateItem: modelsHook.updateProvider,
    deleteItem: modelsHook.deleteProvider,
    refreshData: modelsHook.refreshData
  };

  return (
    <CrudSettingsPage
      config={providersConfig}
      hook={crudHook}
      context={{}}
      getItemId={(item) => item.id}
    />
  );
};
