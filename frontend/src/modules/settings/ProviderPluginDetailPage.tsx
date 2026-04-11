import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PageHeader } from './components/common';
import { listProviderPlugins } from '../../services/api';
import type { ProviderPluginStatus } from '../../types/model';

export const ProviderPluginDetailPage: React.FC = () => {
  const { t } = useTranslation('settings');
  const { pluginId = '' } = useParams<{ pluginId: string }>();
  const decodedPluginId = useMemo(() => decodeURIComponent(pluginId), [pluginId]);

  const [plugin, setPlugin] = useState<ProviderPluginStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const plugins = await listProviderPlugins();
        if (cancelled) {
          return;
        }
        const matchedPlugin = plugins.find((item) => item.id === decodedPluginId) || null;
        setPlugin(matchedPlugin);
        setError(matchedPlugin ? null : `Provider plugin not found: ${decodedPluginId}`);
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
  }, [decodedPluginId]);

  if (loading) {
    return (
      <div data-name="provider-plugin-details-loading" className="text-sm text-gray-600 dark:text-gray-300">
        {t('toolPluginSettings.loading', { defaultValue: 'Loading plugin details...' })}
      </div>
    );
  }

  if (!plugin) {
    return (
      <div data-name="provider-plugin-details-error" className="space-y-3">
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
          {error || `Provider plugin not found: ${decodedPluginId}`}
        </div>
        <Link
          to="/settings/providers"
          className="inline-flex rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
        >
          Back to Providers
        </Link>
      </div>
    );
  }

  return (
    <div data-name="provider-plugin-details-page" className="space-y-6">
      <PageHeader
        title={`Provider Plugin: ${plugin.name}`}
        description={`ID: ${plugin.id}`}
      />

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </div>
      )}

      <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-gray-500 dark:text-gray-400">Plugin ID</dt>
            <dd className="font-mono text-gray-900 dark:text-gray-100">{plugin.id}</dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500 dark:text-gray-400">Version</dt>
            <dd className="text-gray-900 dark:text-gray-100">{plugin.version}</dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500 dark:text-gray-400">Loaded</dt>
            <dd className={plugin.loaded ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}>
              {plugin.loaded ? 'Yes' : 'No'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500 dark:text-gray-400">Enabled</dt>
            <dd className="text-gray-900 dark:text-gray-100">{plugin.enabled ? 'Yes' : 'No'}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs text-gray-500 dark:text-gray-400">Entrypoint</dt>
            <dd className="font-mono text-gray-900 dark:text-gray-100">{plugin.entrypoint}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs text-gray-500 dark:text-gray-400">Plugin Directory</dt>
            <dd className="font-mono text-gray-900 dark:text-gray-100">{plugin.plugin_dir}</dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500 dark:text-gray-400">Adapters</dt>
            <dd className="text-gray-900 dark:text-gray-100">{plugin.adapters_count}</dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500 dark:text-gray-400">Builtin Providers</dt>
            <dd className="text-gray-900 dark:text-gray-100">{plugin.builtin_providers_count}</dd>
          </div>
          {plugin.error && (
            <div className="sm:col-span-2">
              <dt className="text-xs text-gray-500 dark:text-gray-400">Error</dt>
              <dd className="text-red-700 dark:text-red-300">{plugin.error}</dd>
            </div>
          )}
        </dl>
      </section>

      <div>
        <Link
          to="/settings/providers"
          className="inline-flex rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
        >
          Back to Providers
        </Link>
      </div>
    </div>
  );
};
