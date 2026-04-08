import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PageHeader } from './components/common';
import * as api from '../../services/api';
import type { ProjectToolCatalogItem } from '../../types/project';
import type { ToolDescriptionItem, ToolPluginStatus } from '../../services/api';

type ToolRow = ProjectToolCatalogItem & {
  override_description?: string | null;
};

interface ToolGroup {
  key: string;
  label: string;
  version: string | null;
  pluginId: string | null;
  plugin: ToolPluginStatus | null;
  tools: ToolRow[];
}

export const ToolDescriptionsSettings: React.FC = () => {
  const { t } = useTranslation('settings');
  const [toolRows, setToolRows] = useState<ToolRow[]>([]);
  const [pluginsById, setPluginsById] = useState<Record<string, ToolPluginStatus>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const [catalog, descriptions, pluginPayload] = await Promise.all([
          api.getToolCatalog(),
          api.getToolDescriptionsConfig(),
          api.getToolPluginsConfig(),
        ]);
        if (cancelled) {
          return;
        }

        const descriptionMap = new Map<string, ToolDescriptionItem>();
        for (const item of descriptions.tools || []) {
          descriptionMap.set(item.name, item);
        }

        const rows: ToolRow[] = (catalog.tools || []).map((tool) => ({
          ...tool,
          override_description: descriptionMap.get(tool.name)?.override_description,
        }));

        const nextPluginsById: Record<string, ToolPluginStatus> = {};
        for (const plugin of pluginPayload.plugins || []) {
          nextPluginsById[plugin.id] = plugin;
        }

        setToolRows(rows);
        setPluginsById(nextPluginsById);
        setError(null);
      } catch (err) {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const groupedTools = useMemo<ToolGroup[]>(() => {
    const groups = new Map<string, ToolGroup>();
    for (const tool of toolRows) {
      const pluginName = String(tool.plugin_name || '').trim();
      const isBuiltin = pluginName.length === 0;
      const key = isBuiltin ? '__builtin__' : String(tool.plugin_id || pluginName).trim();
      const label = isBuiltin ? t('toolsPage.builtinPluginLabel') : pluginName;
      const version = tool.plugin_version || null;
      const pluginId = isBuiltin ? null : (tool.plugin_id || key);
      const plugin = pluginId ? (pluginsById[pluginId] || null) : null;
      const existing = groups.get(key);
      if (existing) {
        existing.tools.push(tool);
        if (!existing.version && version) {
          existing.version = version;
        }
        continue;
      }
      groups.set(key, {
        key,
        label,
        version,
        pluginId,
        plugin,
        tools: [tool],
      });
    }

    const ordered = Array.from(groups.values()).sort((a, b) => {
      if (a.key === '__builtin__') {
        return -1;
      }
      if (b.key === '__builtin__') {
        return 1;
      }
      return a.label.localeCompare(b.label);
    });

    for (const group of ordered) {
      group.tools.sort((a, b) => a.name.localeCompare(b.name));
    }

    return ordered;
  }, [pluginsById, toolRows, t]);

  if (loading) {
    return (
      <div className="text-sm text-gray-600 dark:text-gray-300" data-name="tool-descriptions-loading">
        {t('toolsPage.loading')}
      </div>
    );
  }

  if (error) {
    return <div className="text-sm text-red-600 dark:text-red-300" data-name="tool-descriptions-error">{error}</div>;
  }

  return (
    <div className="space-y-6" data-name="tool-descriptions-page">
      <PageHeader
        title={t('toolsPage.title')}
        description={t('toolsPage.description')}
      />

      <section className="space-y-4" data-name="tool-description-plugin-groups">
        {groupedTools.map((group) => (
          <div
            key={group.key}
            className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
            data-name="tool-description-plugin-group"
          >
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                {group.label}
                {group.version ? ` (${group.version})` : ''}
              </div>
              <div className="flex items-center gap-2">
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {t('toolsPage.pluginToolsCount', { count: group.tools.length })}
                </div>
                {group.plugin?.has_settings_schema && group.pluginId && (
                  <Link
                    to={`/settings/tools/plugins/${encodeURIComponent(group.pluginId)}`}
                    className="rounded border border-blue-200 bg-blue-50 px-2 py-1 text-[11px] font-medium text-blue-700 hover:bg-blue-100 dark:border-blue-700 dark:bg-blue-900/30 dark:text-blue-200"
                  >
                    {t('toolsPage.pluginSettings')}
                  </Link>
                )}
                {group.plugin?.settings_configured && (
                  <span className="rounded border border-emerald-200 bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300">
                    {t('toolsPage.pluginSettingsConfigured')}
                  </span>
                )}
              </div>
            </div>
            <div className="space-y-2">
              {group.tools.map((tool) => (
                <Link
                  key={tool.name}
                  to={`/settings/tools/${encodeURIComponent(tool.name)}`}
                  className="block rounded-md border border-gray-200 px-3 py-3 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/50"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{tool.name}</div>
                    <div className="text-[11px] text-gray-500 dark:text-gray-400">{tool.group}</div>
                  </div>
                  <div className="mt-1 text-xs text-gray-600 dark:text-gray-300">
                    {tool.description}
                  </div>
                  <div className="mt-2 text-[11px] text-gray-500 dark:text-gray-400">
                    {tool.override_description
                      ? t('toolsPage.customDescriptionConfigured')
                      : t('toolsPage.usingDefaultDescription')}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        ))}
        {groupedTools.length === 0 && (
          <div className="rounded-md border border-dashed border-gray-300 px-3 py-4 text-sm text-gray-500 dark:border-gray-600 dark:text-gray-400">
            {t('toolsPage.empty')}
          </div>
        )}
      </section>
    </div>
  );
};
