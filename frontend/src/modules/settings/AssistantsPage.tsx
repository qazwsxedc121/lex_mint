/**
 * AssistantsPage - Configuration-driven assistant management
 *
 * This page is now powered by the assistantsConfig, reducing boilerplate
 * from 357 lines (AssistantList.tsx) to just ~40 lines.
 */

import React from 'react';
import { useEffect, useState } from 'react';
import { CrudSettingsPage } from './components/crud';
import { assistantsConfig } from './config';
import { useModels } from './hooks/useModels';
import { useAssistants } from './hooks/useAssistants';
import { useKnowledgeBases } from './hooks/useKnowledgeBases';
import type { CrudHook } from './config/types';
import type { Assistant } from '../../types/assistant';
import { getToolCatalog } from '../../services/api';
import type { ProjectToolCatalogItem } from '../../types/project';

export const AssistantsPage: React.FC = () => {
  const modelsHook = useModels();
  const assistantsHook = useAssistants();
  const kbHook = useKnowledgeBases();
  const [toolCatalogItems, setToolCatalogItems] = useState<ProjectToolCatalogItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    const loadToolCatalog = async () => {
      try {
        const catalog = await getToolCatalog();
        if (cancelled) {
          return;
        }
        setToolCatalogItems(Array.isArray(catalog.tools) ? catalog.tools : []);
      } catch (error) {
        console.error('Failed to load tool catalog for assistants page:', error);
      }
    };
    void loadToolCatalog();
    return () => {
      cancelled = true;
    };
  }, []);

  const toolCatalogDefaultMap = toolCatalogItems
    .filter((tool) => tool.group !== 'projectDocuments')
    .reduce<Record<string, boolean>>((acc, tool) => {
      acc[tool.name] = Boolean(tool.enabled_by_default);
      return acc;
    }, {});

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
      context={{
        models: modelsHook.models,
        providers: modelsHook.providers,
        knowledgeBases: kbHook.knowledgeBases,
        toolCatalogItems,
        toolCatalogDefaultMap,
      }}
      getItemId={(item) => item.id}
    />
  );
};
