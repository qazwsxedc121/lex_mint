import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PageHeader, SuccessMessage } from './components/common';
import * as api from '../../services/api';
import type { ToolPluginStatus } from '../../services/api';

interface JsonSchema {
  type?: string | string[];
  title?: string;
  description?: string;
  format?: string;
  enum?: Array<string | number | boolean>;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  items?: JsonSchema;
}

const asRecord = (value: unknown): Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
);

const getSchemaType = (schema: JsonSchema): string => {
  if (Array.isArray(schema.type)) {
    return schema.type.find((item) => item !== 'null') || 'string';
  }
  return schema.type || 'string';
};

const getPathValue = (root: Record<string, unknown>, path: string[]): unknown => {
  let current: unknown = root;
  for (const key of path) {
    if (typeof current !== 'object' || current === null || Array.isArray(current)) {
      return undefined;
    }
    current = (current as Record<string, unknown>)[key];
  }
  return current;
};

const setPathValue = (
  root: Record<string, unknown>,
  path: string[],
  value: unknown,
): Record<string, unknown> => {
  if (path.length === 0) {
    return asRecord(value);
  }
  const [head, ...tail] = path;
  const next = { ...root };
  if (tail.length === 0) {
    next[head] = value;
    return next;
  }
  const child = asRecord(next[head]);
  next[head] = setPathValue(child, tail, value);
  return next;
};

export const ToolPluginSettingsPage: React.FC = () => {
  const { t } = useTranslation('settings');
  const { pluginId = '' } = useParams<{ pluginId: string }>();
  const decodedPluginId = useMemo(() => decodeURIComponent(pluginId), [pluginId]);

  const [plugin, setPlugin] = useState<ToolPluginStatus | null>(null);
  const [schema, setSchema] = useState<JsonSchema | null>(null);
  const [defaults, setDefaults] = useState<Record<string, unknown>>({});
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const [settingsPayload, pluginsPayload] = await Promise.all([
          api.getToolPluginSettings(decodedPluginId),
          api.getToolPluginsConfig(),
        ]);
        if (cancelled) {
          return;
        }
        const nextPlugin = (pluginsPayload.plugins || []).find((item) => item.id === decodedPluginId) || null;
        setPlugin(nextPlugin);
        setSchema(settingsPayload.schema as JsonSchema);
        setDefaults(asRecord(settingsPayload.defaults));
        setFormData(asRecord(settingsPayload.effective_settings));
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
  }, [decodedPluginId]);

  const updateField = (path: string[], value: unknown) => {
    setFormData((current) => setPathValue(current, path, value));
  };

  const validateOnly = async () => {
    setValidating(true);
    setValidationMessage(null);
    try {
      await api.validateToolPluginSettings(decodedPluginId, { settings: formData });
      setValidationMessage(t('toolPluginSettings.valid'));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setValidating(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setValidationMessage(null);
    try {
      await api.updateToolPluginSettings(decodedPluginId, { settings: formData });
      setSaved(true);
      setError(null);
      window.setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const renderField = (
    fieldKey: string,
    fieldSchema: JsonSchema,
    path: string[],
    required: boolean,
  ): React.ReactNode => {
    const schemaType = getSchemaType(fieldSchema);
    const currentValue = getPathValue(formData, path);
    const label = fieldSchema.title || fieldKey;
    const commonLabel = (
      <div className="text-xs text-gray-700 dark:text-gray-300">
        {label}
        {required ? ' *' : ''}
      </div>
    );

    if (schemaType === 'object' && fieldSchema.properties) {
      const nestedRequired = new Set(fieldSchema.required || []);
      return (
        <div key={path.join('.')} className="rounded-md border border-gray-200 p-3 dark:border-gray-700">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</div>
          <div className="space-y-3">
            {Object.entries(fieldSchema.properties).map(([childKey, childSchema]) =>
              renderField(
                childKey,
                childSchema,
                [...path, childKey],
                nestedRequired.has(childKey),
              ))}
          </div>
        </div>
      );
    }

    if (fieldSchema.enum && fieldSchema.enum.length > 0) {
      return (
        <label key={path.join('.')} className="block space-y-1">
          {commonLabel}
          <select
            value={currentValue === undefined ? '' : String(currentValue)}
            onChange={(event) => updateField(path, event.target.value)}
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
          >
            <option value="">{t('toolPluginSettings.selectPlaceholder')}</option>
            {fieldSchema.enum.map((item) => (
              <option key={String(item)} value={String(item)}>{String(item)}</option>
            ))}
          </select>
          {fieldSchema.description && <p className="text-[11px] text-gray-500 dark:text-gray-400">{fieldSchema.description}</p>}
        </label>
      );
    }

    if (schemaType === 'boolean') {
      return (
        <label key={path.join('.')} className="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2 dark:border-gray-700">
          <span className="text-sm text-gray-800 dark:text-gray-200">{label}</span>
          <input
            type="checkbox"
            checked={Boolean(currentValue)}
            onChange={(event) => updateField(path, event.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-blue-600"
          />
        </label>
      );
    }

    if (schemaType === 'number' || schemaType === 'integer') {
      return (
        <label key={path.join('.')} className="block space-y-1">
          {commonLabel}
          <input
            type="number"
            value={currentValue === undefined || currentValue === null ? '' : String(currentValue)}
            step={schemaType === 'integer' ? 1 : 'any'}
            onChange={(event) => {
              const nextRaw = event.target.value.trim();
              if (!nextRaw) {
                updateField(path, undefined);
                return;
              }
              const parsed = schemaType === 'integer'
                ? Number.parseInt(nextRaw, 10)
                : Number.parseFloat(nextRaw);
              updateField(path, Number.isFinite(parsed) ? parsed : undefined);
            }}
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
          />
          {fieldSchema.description && <p className="text-[11px] text-gray-500 dark:text-gray-400">{fieldSchema.description}</p>}
        </label>
      );
    }

    if (schemaType === 'array' || schemaType === 'object') {
      const display = currentValue === undefined ? '' : JSON.stringify(currentValue, null, 2);
      return (
        <label key={path.join('.')} className="block space-y-1">
          {commonLabel}
          <textarea
            rows={6}
            value={display}
            onChange={(event) => {
              const nextRaw = event.target.value.trim();
              if (!nextRaw) {
                updateField(path, schemaType === 'array' ? [] : {});
                return;
              }
              try {
                const parsed = JSON.parse(nextRaw);
                updateField(path, parsed);
              } catch {
                updateField(path, nextRaw);
              }
            }}
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-mono dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
          />
          <p className="text-[11px] text-gray-500 dark:text-gray-400">{t('toolPluginSettings.jsonHint')}</p>
        </label>
      );
    }

    return (
      <label key={path.join('.')} className="block space-y-1">
        {commonLabel}
        <input
          type={fieldSchema.format === 'password' ? 'password' : 'text'}
          value={currentValue === undefined || currentValue === null ? '' : String(currentValue)}
          onChange={(event) => updateField(path, event.target.value)}
          className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
        />
        {fieldSchema.description && <p className="text-[11px] text-gray-500 dark:text-gray-400">{fieldSchema.description}</p>}
      </label>
    );
  };

  const topSchema = schema || {};
  const topProperties = topSchema.properties || {};
  const topRequired = new Set(topSchema.required || []);

  if (loading) {
    return (
      <div className="text-sm text-gray-600 dark:text-gray-300" data-name="tool-plugin-settings-loading">
        {t('toolPluginSettings.loading')}
      </div>
    );
  }

  if (!schema) {
    return (
      <div className="text-sm text-red-600 dark:text-red-300" data-name="tool-plugin-settings-error">
        {error || t('toolPluginSettings.noSchema')}
      </div>
    );
  }

  return (
    <div className="space-y-6" data-name="tool-plugin-settings-page">
      <PageHeader
        title={t('toolPluginSettings.title', { name: plugin?.name || decodedPluginId })}
        description={t('toolPluginSettings.description')}
      />

      {saved && <SuccessMessage message={t('toolPluginSettings.savedSuccess')} />}
      {validationMessage && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300">
          {validationMessage}
        </div>
      )}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </div>
      )}

      <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{t('toolPluginSettings.defaults')}</div>
        <pre className="max-h-48 overflow-auto rounded border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300">
          {JSON.stringify(defaults, null, 2)}
        </pre>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
        <div className="space-y-4">
          {Object.entries(topProperties).map(([key, childSchema]) =>
            renderField(key, childSchema, [key], topRequired.has(key)))}
          {Object.keys(topProperties).length === 0 && (
            <div className="rounded-md border border-dashed border-gray-300 px-3 py-4 text-sm text-gray-500 dark:border-gray-600 dark:text-gray-400">
              {t('toolPluginSettings.noEditableFields')}
            </div>
          )}
        </div>
      </section>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? t('toolPluginSettings.saving') : t('toolPluginSettings.save')}
        </button>
        <button
          type="button"
          onClick={() => void validateOnly()}
          disabled={validating || saving}
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
        >
          {validating ? t('toolPluginSettings.validating') : t('toolPluginSettings.validate')}
        </button>
        <Link
          to="/settings/tools"
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
        >
          {t('toolPluginSettings.backToTools')}
        </Link>
      </div>
    </div>
  );
};
