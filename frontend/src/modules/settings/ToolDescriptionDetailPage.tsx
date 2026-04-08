import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { PageHeader, SuccessMessage } from './components/common';
import * as api from '../../services/api';
import type { ToolDescriptionItem } from '../../services/api';

export const ToolDescriptionDetailPage: React.FC = () => {
  const { toolName = '' } = useParams<{ toolName: string }>();
  const decodedToolName = useMemo(() => decodeURIComponent(toolName), [toolName]);

  const [item, setItem] = useState<ToolDescriptionItem | null>(null);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const payload = await api.getToolDescriptionsConfig();
      const nextItem = (payload.tools || []).find((tool) => tool.name === decodedToolName) || null;
      setItem(nextItem);
      setDraft(nextItem?.override_description || '');
      setError(nextItem ? null : `Tool not found: ${decodedToolName}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decodedToolName]);

  const isDirty = (item?.override_description || '') !== draft;

  const save = async () => {
    if (!item) {
      return;
    }
    setSaving(true);
    try {
      const trimmed = draft.trim();
      await api.updateToolDescriptionsConfig({
        overrides: {
          [item.name]: trimmed.length > 0 ? trimmed : null,
        },
      });
      await load();
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-sm text-gray-600 dark:text-gray-300" data-name="tool-description-detail-loading">Loading tool...</div>;
  }

  if (!item) {
    return <div className="text-sm text-red-600 dark:text-red-300" data-name="tool-description-detail-error">{error || 'Tool not found'}</div>;
  }

  return (
    <div className="space-y-6" data-name="tool-description-detail-page">
      <PageHeader
        title={`Tool: ${item.name}`}
        description="Edit model-facing guidance for this tool."
      />

      {saved && <SuccessMessage message="Saved successfully" />}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </div>
      )}

      <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800" data-name="tool-description-detail-meta">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Group</div>
            <div className="text-sm text-gray-900 dark:text-gray-100">{item.group}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Source</div>
            <div className="text-sm text-gray-900 dark:text-gray-100">{item.source}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Plugin</div>
            <div className="text-sm text-gray-900 dark:text-gray-100">{item.plugin_name || item.plugin_id || '-'}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Version</div>
            <div className="text-sm text-gray-900 dark:text-gray-100">{item.plugin_version || '-'}</div>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800" data-name="tool-description-default">
        <div className="text-xs text-gray-500 dark:text-gray-400">Default description</div>
        <div className="mt-2 rounded border border-gray-200 bg-gray-50 px-3 py-3 text-sm text-gray-800 dark:border-gray-600 dark:bg-gray-700/40 dark:text-gray-200">
          {item.default_description}
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800" data-name="tool-description-override">
        <div className="text-xs text-gray-500 dark:text-gray-400">Custom description</div>
        <textarea
          rows={8}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Leave empty to use default description."
          className="mt-2 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
        />
      </section>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving || !isDirty}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button
          type="button"
          onClick={() => setDraft('')}
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
        >
          Restore Default
        </button>
        <Link
          to="/settings/tools"
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
        >
          Back to Tools
        </Link>
      </div>
    </div>
  );
};
