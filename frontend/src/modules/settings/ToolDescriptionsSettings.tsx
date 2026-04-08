import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from './components/common';
import * as api from '../../services/api';
import type { ProjectToolCatalogItem } from '../../types/project';
import type { ToolDescriptionItem, ToolPluginStatus } from '../../services/api';

type ToolRow = ProjectToolCatalogItem & {
  override_description?: string | null;
};

export const ToolDescriptionsSettings: React.FC = () => {
  const [toolRows, setToolRows] = useState<ToolRow[]>([]);
  const [plugins, setPlugins] = useState<ToolPluginStatus[]>([]);
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

        setToolRows(rows);
        setPlugins(pluginPayload.plugins || []);
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

  const pluginLoadedCount = useMemo(
    () => plugins.filter((item) => item.loaded).length,
    [plugins],
  );

  if (loading) {
    return <div className="text-sm text-gray-600 dark:text-gray-300" data-name="tool-descriptions-loading">Loading tool settings...</div>;
  }

  if (error) {
    return <div className="text-sm text-red-600 dark:text-red-300" data-name="tool-descriptions-error">{error}</div>;
  }

  return (
    <div className="space-y-6" data-name="tool-descriptions-page">
      <PageHeader
        title="Tool Configurations"
        description="Configure tool descriptions and inspect plugin load status. Click one tool to edit."
      />

      <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800" data-name="tool-plugin-summary">
        <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Plugins</div>
        <div className="mt-2 text-xs text-gray-600 dark:text-gray-300">
          Loaded {pluginLoadedCount} / {plugins.length}
        </div>
        <div className="mt-3 space-y-2">
          {plugins.map((plugin) => (
            <div key={plugin.id} className="rounded-md border border-gray-200 px-3 py-2 text-xs dark:border-gray-700">
              <div className="font-medium text-gray-900 dark:text-gray-100">{plugin.name} ({plugin.version})</div>
              <div className={plugin.loaded ? 'text-emerald-600 dark:text-emerald-300' : 'text-red-600 dark:text-red-300'}>
                {plugin.loaded ? 'Loaded' : `Failed: ${plugin.error || 'unknown error'}`}
              </div>
              <div className="text-gray-500 dark:text-gray-400">{plugin.entrypoint}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800" data-name="tool-description-list">
        <div className="mb-3 text-sm font-semibold text-gray-900 dark:text-gray-100">Tools</div>
        <div className="space-y-2">
          {toolRows.map((tool) => (
            <Link
              key={tool.name}
              to={`/settings/tools/${encodeURIComponent(tool.name)}`}
              className="block rounded-md border border-gray-200 px-3 py-3 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/50"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{tool.name}</div>
                <div className="text-[11px] text-gray-500 dark:text-gray-400">{tool.plugin_name || tool.source}</div>
              </div>
              <div className="mt-1 text-xs text-gray-600 dark:text-gray-300">
                {tool.description}
              </div>
              <div className="mt-2 text-[11px] text-gray-500 dark:text-gray-400">
                {tool.override_description ? 'Custom description configured' : 'Using default description'}
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
};
