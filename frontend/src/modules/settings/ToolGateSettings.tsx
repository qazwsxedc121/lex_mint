import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PageHeader, SuccessMessage } from './components/common';
import * as api from '../../services/api';
import type { ToolGateConfig, ToolGateRule } from '../../services/api';
import type { ProjectToolCatalogItem } from '../../types/project';

const EMPTY_RULE: ToolGateRule = {
  id: '',
  enabled: true,
  priority: 0,
  pattern: '',
  flags: '',
  include_tools: [],
  exclude_tools: [],
  description: '',
};

export const ToolGateSettings: React.FC = () => {
  const { t } = useTranslation('settings');
  const [config, setConfig] = useState<ToolGateConfig | null>(null);
  const [toolCatalogItems, setToolCatalogItems] = useState<ProjectToolCatalogItem[]>([]);
  const [toolCatalogError, setToolCatalogError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const next = await api.getToolGateConfig();
      setConfig(next);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadConfig();
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadToolCatalog = async () => {
      try {
        const catalog = await api.getToolCatalog();
        if (cancelled) {
          return;
        }
        setToolCatalogItems(Array.isArray(catalog.tools) ? catalog.tools : []);
        setToolCatalogError(null);
      } catch (err) {
        if (cancelled) {
          return;
        }
        setToolCatalogItems([]);
        setToolCatalogError(err instanceof Error ? err.message : String(err));
      }
    };
    void loadToolCatalog();
    return () => {
      cancelled = true;
    };
  }, []);

  const updateConfig = (patch: Partial<ToolGateConfig>) => {
    setConfig((current) => {
      if (!current) {
        return current;
      }
      return { ...current, ...patch };
    });
  };

  const updateRule = (index: number, patch: Partial<ToolGateRule>) => {
    setConfig((current) => {
      if (!current) {
        return current;
      }
      const nextRules = [...current.rules];
      nextRules[index] = { ...nextRules[index], ...patch };
      return { ...current, rules: nextRules };
    });
  };

  const addRule = () => {
    setConfig((current) => {
      if (!current) {
        return current;
      }
      const nextRule: ToolGateRule = {
        ...EMPTY_RULE,
        id: `rule_${Date.now()}`,
      };
      return { ...current, rules: [...current.rules, nextRule] };
    });
  };

  const removeRule = (index: number) => {
    setConfig((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        rules: current.rules.filter((_, i) => i !== index),
      };
    });
  };

  const toggleRuleTool = (ruleIndex: number, field: 'include_tools' | 'exclude_tools', toolName: string) => {
    const rule = config?.rules[ruleIndex];
    if (!rule) {
      return;
    }
    const current = field === 'include_tools' ? rule.include_tools : rule.exclude_tools;
    const next = current.includes(toolName)
      ? current.filter((item) => item !== toolName)
      : [...current, toolName];
    updateRule(ruleIndex, { [field]: next });
  };

  const getRuleToolOptions = (rule: ToolGateRule): string[] => {
    const names = toolCatalogItems.map((item) => item.name);
    return Array.from(new Set([...names, ...rule.include_tools, ...rule.exclude_tools]));
  };

  const handleSave = async () => {
    if (!config) {
      return;
    }
    setSaving(true);
    try {
      await api.updateToolGateConfig(config);
      setSaved(true);
      setError(null);
      window.setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="text-sm text-gray-600 dark:text-gray-300" data-name="tool-gate-settings-loading">
        {t('config.loadingSettings')}
      </div>
    );
  }

  if (!config) {
    return (
      <div className="text-sm text-red-600 dark:text-red-300" data-name="tool-gate-settings-error">
        {error || t('config.failedToLoad')}
      </div>
    );
  }

  return (
    <div className="space-y-6" data-name="tool-gate-settings-page">
      <PageHeader title={t('toolGate.title')} description={t('toolGate.description')} />

      {saved && <SuccessMessage message={t('config.savedSuccess')} />}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </div>
      )}

      <section
        className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
        data-name="tool-gate-general"
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2 dark:border-gray-700">
            <span className="text-sm text-gray-800 dark:text-gray-200">{t('toolGate.enabled')}</span>
            <input
              type="checkbox"
              checked={config.enabled}
              onChange={(event) => updateConfig({ enabled: event.target.checked })}
              className="h-4 w-4 rounded border-gray-300 text-blue-600"
            />
          </label>
        </div>
      </section>

      <section
        className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
        data-name="tool-gate-rules"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('toolGate.rules')}</h2>
          <button
            type="button"
            onClick={addRule}
            className="rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 dark:border-blue-700 dark:bg-blue-900/30 dark:text-blue-200"
          >
            {t('toolGate.addRule')}
          </button>
        </div>

        <div className="space-y-4">
          {config.rules.length === 0 && (
            <div className="rounded-md border border-dashed border-gray-300 px-3 py-4 text-sm text-gray-500 dark:border-gray-600 dark:text-gray-400">
              {t('toolGate.noRules')}
            </div>
          )}
          {config.rules.map((rule, index) => (
            <div key={`${rule.id}-${index}`} className="rounded-md border border-gray-200 p-3 dark:border-gray-700">
              <div className="mb-3 flex items-center justify-between">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  {t('toolGate.rule')} #{index + 1}
                </div>
                <button
                  type="button"
                  onClick={() => removeRule(index)}
                  className="rounded border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/30"
                >
                  {t('toolGate.removeRule')}
                </button>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <label>
                  <div className="text-xs text-gray-700 dark:text-gray-300">{t('toolGate.ruleId')}</div>
                  <input
                    value={rule.id}
                    onChange={(event) => updateRule(index, { id: event.target.value })}
                    className="mt-1 w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
                  />
                </label>
                <label className="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2 dark:border-gray-700">
                  <span className="text-xs text-gray-700 dark:text-gray-300">{t('toolGate.ruleEnabled')}</span>
                  <input
                    type="checkbox"
                    checked={rule.enabled}
                    onChange={(event) => updateRule(index, { enabled: event.target.checked })}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600"
                  />
                </label>
                <label>
                  <div className="text-xs text-gray-700 dark:text-gray-300">{t('toolGate.priority')}</div>
                  <input
                    type="number"
                    value={rule.priority}
                    onChange={(event) => updateRule(index, { priority: Number.parseInt(event.target.value, 10) || 0 })}
                    className="mt-1 w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
                  />
                </label>
                <label>
                  <div className="text-xs text-gray-700 dark:text-gray-300">{t('toolGate.flags')}</div>
                  <input
                    value={rule.flags}
                    onChange={(event) => updateRule(index, { flags: event.target.value })}
                    className="mt-1 w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
                  />
                </label>

                <label className="md:col-span-2">
                  <div className="text-xs text-gray-700 dark:text-gray-300">{t('toolGate.pattern')}</div>
                  <textarea
                    rows={2}
                    value={rule.pattern}
                    onChange={(event) => updateRule(index, { pattern: event.target.value })}
                    className="mt-1 w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm font-mono dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
                  />
                </label>

                <label>
                  <div className="text-xs text-gray-700 dark:text-gray-300">{t('toolGate.includeTools')}</div>
                  <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">{t('toolGate.includeToolsHelp')}</p>
                  <div className="mt-1 max-h-44 space-y-1 overflow-y-auto rounded-md border border-gray-300 bg-white p-2 dark:border-gray-600 dark:bg-gray-700">
                    {getRuleToolOptions(rule).map((toolName) => (
                      <label
                        key={`include-${rule.id}-${toolName}`}
                        className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-gray-50 dark:hover:bg-gray-600"
                      >
                        <input
                          type="checkbox"
                          checked={rule.include_tools.includes(toolName)}
                          onChange={() => toggleRuleTool(index, 'include_tools', toolName)}
                          className="h-4 w-4 rounded border-gray-300 text-blue-600"
                        />
                        <span className="text-xs text-gray-800 dark:text-gray-200">{toolName}</span>
                      </label>
                    ))}
                    {getRuleToolOptions(rule).length === 0 && (
                      <div className="px-2 py-1 text-xs text-gray-500 dark:text-gray-400">{t('toolGate.noToolCatalog')}</div>
                    )}
                  </div>
                </label>

                <label>
                  <div className="text-xs text-gray-700 dark:text-gray-300">{t('toolGate.excludeTools')}</div>
                  <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">{t('toolGate.excludeToolsHelp')}</p>
                  <div className="mt-1 max-h-44 space-y-1 overflow-y-auto rounded-md border border-gray-300 bg-white p-2 dark:border-gray-600 dark:bg-gray-700">
                    {getRuleToolOptions(rule).map((toolName) => (
                      <label
                        key={`exclude-${rule.id}-${toolName}`}
                        className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-gray-50 dark:hover:bg-gray-600"
                      >
                        <input
                          type="checkbox"
                          checked={rule.exclude_tools.includes(toolName)}
                          onChange={() => toggleRuleTool(index, 'exclude_tools', toolName)}
                          className="h-4 w-4 rounded border-gray-300 text-blue-600"
                        />
                        <span className="text-xs text-gray-800 dark:text-gray-200">{toolName}</span>
                      </label>
                    ))}
                    {getRuleToolOptions(rule).length === 0 && (
                      <div className="px-2 py-1 text-xs text-gray-500 dark:text-gray-400">{t('toolGate.noToolCatalog')}</div>
                    )}
                  </div>
                </label>

                <label className="md:col-span-2">
                  <div className="text-xs text-gray-700 dark:text-gray-300">{t('toolGate.descriptionField')}</div>
                  <input
                    value={rule.description || ''}
                    onChange={(event) => updateRule(index, { description: event.target.value })}
                    className="mt-1 w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
                  />
                </label>
              </div>
            </div>
          ))}
        </div>
      </section>

      {toolCatalogError && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
          {t('toolGate.toolCatalogLoadFailed')}: {toolCatalogError}
        </div>
      )}

      <div className="flex items-center gap-2" data-name="tool-gate-actions">
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? t('toolGate.saving') : t('toolGate.saveRules')}
        </button>
        <button
          type="button"
          onClick={() => {
            void loadConfig();
          }}
          disabled={saving}
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
        >
          {t('toolGate.reload')}
        </button>
      </div>
    </div>
  );
};
