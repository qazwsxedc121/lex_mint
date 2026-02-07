/**
 * Settings CRUD pages factory exports
 */

import type { Assistant } from '../../types/assistant';
import type { Model, Provider } from '../../types/model';
import type { CrudHook } from './config/types';
import { assistantsConfig, modelsConfig, providersConfig } from './config';
import { makeCrudPages } from './components/crud';
import { useAssistants } from './hooks/useAssistants';
import { useModels } from './hooks/useModels';

const useAssistantsCrud = () => {
  const modelsHook = useModels();
  const assistantsHook = useAssistants();

  const hook: CrudHook<Assistant> = {
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

  return {
    hook,
    context: { models: modelsHook.models, providers: modelsHook.providers }
  };
};

const useModelsCrud = () => {
  const modelsHook = useModels();

  const hook: CrudHook<Model> = {
    items: modelsHook.models,
    loading: modelsHook.loading,
    error: modelsHook.error,
    createItem: modelsHook.createModel,
    updateItem: (id, data) => modelsHook.updateModel(id, data as Model),
    deleteItem: modelsHook.deleteModel,
    refreshData: modelsHook.refreshData
  };

  return {
    hook,
    context: { providers: modelsHook.providers },
    getItemId: (item: Model) => `${item.provider_id}:${item.id}`
  };
};

const useProvidersCrud = () => {
  const modelsHook = useModels();

  const hook: CrudHook<Provider> = {
    items: modelsHook.providers,
    loading: modelsHook.loading,
    error: modelsHook.error,
    createItem: modelsHook.createProvider,
    updateItem: modelsHook.updateProvider,
    deleteItem: modelsHook.deleteProvider,
    refreshData: modelsHook.refreshData
  };

  return { hook, context: {} };
};

const assistantsPages = makeCrudPages<Assistant>({
  config: assistantsConfig,
  useData: useAssistantsCrud,
  backPath: '/settings/assistants',
  idParam: 'assistantId',
  missingMessage: 'Assistant not found'
});

const modelsPages = makeCrudPages<Model>({
  config: modelsConfig,
  useData: useModelsCrud,
  backPath: '/settings/models',
  idParam: 'modelId',
  decodeId: (value) => decodeURIComponent(value),
  missingMessage: 'Model not found'
});

const providersPages = makeCrudPages<Provider>({
  config: providersConfig,
  useData: useProvidersCrud,
  backPath: '/settings/providers',
  idParam: 'providerId',
  missingMessage: 'Provider not found'
});

export const AssistantsCreatePage = assistantsPages.CreatePage;
export const AssistantsEditPage = assistantsPages.EditPage;
export const ModelsCreatePage = modelsPages.CreatePage;
export const ModelsEditPage = modelsPages.EditPage;
export const ProvidersCreatePage = providersPages.CreatePage;
export const ProvidersEditPage = providersPages.EditPage;
