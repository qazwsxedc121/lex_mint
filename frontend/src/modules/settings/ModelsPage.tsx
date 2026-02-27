/**
 * ModelsPage - Configuration-driven model management
 *
 * This page is now powered by the modelsConfig, reducing boilerplate
 * from 424 lines (ModelList.tsx) to just ~35 lines.
 */

import React from 'react';
import { useMemo, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CrudSettingsPage } from './components/crud';
import { modelsConfig } from './config';
import { useModels } from './hooks/useModels';
import type { CrudHook } from './config/types';
import type { Model } from '../../types/model';

const MODELS_PROVIDER_FILTER_KEY = 'settings.models.selectedProvider';
const MODELS_TAG_FILTER_KEY = 'settings.models.selectedTag';

const normalizeTags = (rawTags: unknown): string[] => {
  if (Array.isArray(rawTags)) {
    return rawTags
      .map((tag) => String(tag).trim().toLowerCase())
      .filter(Boolean);
  }
  if (typeof rawTags === 'string') {
    return rawTags
      .split(',')
      .map((tag) => tag.trim().toLowerCase())
      .filter(Boolean);
  }
  return [];
};

export const ModelsPage: React.FC = () => {
  const { t } = useTranslation('settings');
  const modelsHook = useModels();
  const [selectedProvider, setSelectedProvider] = useState<string>('all');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  const providerTabs = useMemo(() => {
    const providers = modelsHook.providers || [];
    return providers
      .filter((provider) => provider.enabled || modelsHook.models.some((model) => model.provider_id === provider.id))
      .map((provider) => ({
        id: provider.id,
        name: provider.name,
        count: modelsHook.models.filter((model) => model.provider_id === provider.id).length,
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [modelsHook.providers, modelsHook.models]);

  useEffect(() => {
    const saved = localStorage.getItem(MODELS_PROVIDER_FILTER_KEY);
    if (saved && (saved === 'all' || providerTabs.some((provider) => provider.id === saved))) {
      setSelectedProvider(saved);
      return;
    }

    const defaultProviderId = modelsHook.defaultConfig?.provider;
    if (defaultProviderId && providerTabs.some((provider) => provider.id === defaultProviderId)) {
      setSelectedProvider(defaultProviderId);
      return;
    }

    if (providerTabs.length > 0) {
      setSelectedProvider(providerTabs[0].id);
    } else {
      setSelectedProvider('all');
    }
  }, [modelsHook.defaultConfig, providerTabs]);

  useEffect(() => {
    localStorage.setItem(MODELS_PROVIDER_FILTER_KEY, selectedProvider);
  }, [selectedProvider]);

  const providerFilteredModels = useMemo(() => {
    if (selectedProvider === 'all') {
      return modelsHook.models;
    }
    return modelsHook.models.filter((model) => model.provider_id === selectedProvider);
  }, [modelsHook.models, selectedProvider]);

  const tagTabs = useMemo(() => {
    const tagCount = new Map<string, number>();

    providerFilteredModels.forEach((model) => {
      const modelTags = Array.from(new Set(normalizeTags(model.tags)));
      modelTags.forEach((tag) => {
        tagCount.set(tag, (tagCount.get(tag) || 0) + 1);
      });
    });

    return Array.from(tagCount.entries())
      .map(([id, count]) => ({ id, name: id, count }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [providerFilteredModels]);

  useEffect(() => {
    const saved = localStorage.getItem(MODELS_TAG_FILTER_KEY);
    if (saved) {
      let parsed: string[] = [];
      try {
        const raw = JSON.parse(saved);
        if (Array.isArray(raw)) {
          parsed = raw.map((tag) => String(tag).trim().toLowerCase()).filter(Boolean);
        }
      } catch {
        // Backward compatibility: old value is a single selected tag
        if (saved !== 'all') {
          parsed = [saved];
        }
      }

      const available = new Set(tagTabs.map((tag) => tag.id));
      const filtered = parsed.filter((tag) => available.has(tag));
      setSelectedTags(Array.from(new Set(filtered)));
      return;
    }
    setSelectedTags([]);
  }, [tagTabs]);

  useEffect(() => {
    localStorage.setItem(MODELS_TAG_FILTER_KEY, JSON.stringify(selectedTags));
  }, [selectedTags]);

  const filteredModels = useMemo(() => {
    if (selectedTags.length === 0) {
      return providerFilteredModels;
    }
    return providerFilteredModels.filter((model) => {
      const tags = normalizeTags(model.tags);
      return selectedTags.every((selectedTag) => tags.includes(selectedTag));
    });
  }, [providerFilteredModels, selectedTags]);

  const defaultModelId = useMemo(() => {
    if (!modelsHook.defaultConfig) {
      return null;
    }
    return `${modelsHook.defaultConfig.provider}:${modelsHook.defaultConfig.model}`;
  }, [modelsHook.defaultConfig]);

  // Adapt useModels hook to CrudHook interface
  const crudHook: CrudHook<Model> = {
    items: filteredModels,
    defaultItemId: defaultModelId,
    loading: modelsHook.loading,
    error: modelsHook.error,
    createItem: modelsHook.createModel,
    updateItem: (id, data) => {
      // Models use composite key provider_id:id
      return modelsHook.updateModel(id, data as Model);
    },
    deleteItem: modelsHook.deleteModel,
    setDefault: async (id: string) => {
      const separator = id.indexOf(':');
      if (separator <= 0 || separator === id.length - 1) {
        throw new Error(`Invalid model id: ${id}`);
      }
      const providerId = id.slice(0, separator);
      const modelId = id.slice(separator + 1);
      await modelsHook.setDefault(providerId, modelId);
    },
    refreshData: modelsHook.refreshData
  };

  return (
    <div className="space-y-4" data-name="models-page-with-provider-filter">
      <div
        className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800"
        data-name="models-provider-filter"
      >
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
          {t('models.providerFilter')}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSelectedProvider('all')}
            className={`rounded-md px-3 py-1.5 text-sm ${
              selectedProvider === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            {t('models.providerAll')} ({modelsHook.models.length})
          </button>
          {providerTabs.map((provider) => (
            <button
              key={provider.id}
              type="button"
              onClick={() => setSelectedProvider(provider.id)}
              className={`rounded-md px-3 py-1.5 text-sm ${
                selectedProvider === provider.id
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {provider.name} ({provider.count})
            </button>
          ))}
        </div>

        <div className="mt-4 border-t border-gray-200 pt-3 dark:border-gray-700">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
            {t('models.tagFilter')}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setSelectedTags([])}
              className={`rounded-md px-3 py-1.5 text-sm ${
                selectedTags.length === 0
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {t('models.tagAll')} ({providerFilteredModels.length})
            </button>
            {tagTabs.map((tag) => (
              <button
                key={tag.id}
                type="button"
                onClick={() =>
                  setSelectedTags((current) =>
                    current.includes(tag.id)
                      ? current.filter((item) => item !== tag.id)
                      : [...current, tag.id]
                  )
                }
                className={`rounded-md px-3 py-1.5 text-sm ${
                  selectedTags.includes(tag.id)
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                {tag.name} ({tag.count})
              </button>
            ))}
          </div>
        </div>
      </div>

      <CrudSettingsPage
        config={modelsConfig}
        hook={crudHook}
        context={{ providers: modelsHook.providers, selectedProvider, selectedTags }}
        getItemId={(item) => `${item.provider_id}:${item.id}`}
      />
    </div>
  );
};
