
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PageHeader, SettingsHelp } from './components/common';
import * as api from '../../services/api';
import type {
  MemoryCreateRequest,
  MemoryItem,
  MemoryScope,
  MemorySettings as MemorySettingsData,
  MemorySettingsUpdate,
} from '../../types/memory';
import type { Assistant } from '../../types/assistant';

const LAYERS = ['fact', 'instruction'];
type ScopeFilter = 'all' | MemoryScope;
type SortMode = 'updated' | 'created' | 'score' | 'importance' | 'confidence' | 'hit';

const DEFAULT_CREATE_FORM: MemoryCreateRequest = {
  content: '',
  scope: 'global',
  layer: 'fact',
  confidence: 0.8,
  importance: 0.6,
  pinned: false,
};

const parseApiError = (error: unknown, fallback: string): string => {
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  if (error instanceof Error) return error.message;
  return fallback;
};

const formatDate = (value?: string | null): string => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const formatNum = (value?: number | null, digits: number = 2): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return value.toFixed(digits);
};

const fieldClassName =
  'w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white';
const selectClassName = fieldClassName;
const compactFieldClassName =
  'w-24 rounded-md border border-gray-300 bg-white px-2 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white';

export const MemorySettings: React.FC = () => {
  const { t } = useTranslation('settings');

  const tr = useCallback(
    (key: string, defaultValue: string, options?: Record<string, unknown>) =>
      t(key, { defaultValue, ...(options || {}) }),
    [t],
  );

  const [loadingPage, setLoadingPage] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [draft, setDraft] = useState<MemorySettingsData | null>(null);
  const [assistants, setAssistants] = useState<Assistant[]>([]);

  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>('all');
  const [assistantFilter, setAssistantFilter] = useState('');
  const [layerFilter, setLayerFilter] = useState('all');
  const [showInactive, setShowInactive] = useState(false);
  const [limit, setLimit] = useState(120);
  const [query, setQuery] = useState('');
  const [sortMode, setSortMode] = useState<SortMode>('updated');
  const [showMetadataJson, setShowMetadataJson] = useState(true);
  const [searchContext, setSearchContext] = useState('');
  const [resultCount, setResultCount] = useState(0);

  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [createForm, setCreateForm] = useState<MemoryCreateRequest>(DEFAULT_CREATE_FORM);

  const sortedAssistants = useMemo(
    () => [...assistants].sort((a, b) => a.name.localeCompare(b.name)),
    [assistants],
  );

  const assistantNameMap = useMemo(
    () => sortedAssistants.reduce<Record<string, string>>((acc, assistant) => {
      acc[assistant.id] = assistant.name;
      return acc;
    }, {}),
    [sortedAssistants],
  );

  const sortedMemories = useMemo(() => {
    const items = [...memories];
    switch (sortMode) {
      case 'created':
        items.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
        break;
      case 'score':
        items.sort((a, b) => (b.score || 0) - (a.score || 0));
        break;
      case 'importance':
        items.sort((a, b) => (b.importance || 0) - (a.importance || 0));
        break;
      case 'confidence':
        items.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
        break;
      case 'hit':
        items.sort((a, b) => (b.hit_count || 0) - (a.hit_count || 0));
        break;
      case 'updated':
      default:
        items.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''));
        break;
    }
    return items;
  }, [memories, sortMode]);

  const stats = useMemo(() => ({
    total: sortedMemories.length,
    active: sortedMemories.filter((item) => item.is_active !== false).length,
    inactive: sortedMemories.filter((item) => item.is_active === false).length,
    pinned: sortedMemories.filter((item) => item.pinned).length,
    global: sortedMemories.filter((item) => item.scope === 'global').length,
    assistant: sortedMemories.filter((item) => item.scope === 'assistant').length,
  }), [sortedMemories]);

  const getScopeLabel = useCallback((scope?: string | null) => {
    if (scope === 'global') return tr('memory.options.scopeGlobal', 'global');
    if (scope === 'assistant') return tr('memory.options.scopeAssistant', 'assistant');
    return scope || '-';
  }, [tr]);

  const getLayerLabel = useCallback((layer?: string | null) => {
    if (!layer) return '-';
    return tr(`memory.layers.${layer}`, layer);
  }, [tr]);

  const clearStatus = useCallback(() => {
    setError(null);
    setMessage(null);
  }, []);

  const loadBaseData = useCallback(async () => {
    clearStatus();
    setLoadingPage(true);
    try {
      const [memorySettings, assistantsData] = await Promise.all([
        api.getMemorySettings(),
        api.listAssistants(),
      ]);
      setDraft(memorySettings);
      setAssistants(assistantsData);
      setCreateForm((prev) => ({
        ...prev,
        profile_id: prev.profile_id || memorySettings.profile_id,
      }));
    } catch (err) {
      setError(parseApiError(err, tr('memory.errors.loadSettings', 'Failed to load memory settings')));
    } finally {
      setLoadingPage(false);
    }
  }, [clearStatus, tr]);

  const loadMemories = useCallback(async () => {
    clearStatus();
    setLoadingList(true);
    try {
      const trimmed = query.trim();
      const maxLimit = Math.max(1, Math.min(500, limit || 120));

      if (trimmed && !(scopeFilter === 'assistant' && !assistantFilter)) {
        const response = await api.searchMemories({
          query: trimmed,
          assistant_id: assistantFilter || undefined,
          scope: scopeFilter === 'all' ? undefined : scopeFilter,
          layer: layerFilter === 'all' ? undefined : layerFilter,
          include_global: true,
          include_assistant: true,
          limit: Math.min(20, maxLimit),
        });
        const items = response.items || [];
        setMemories(items);
        setResultCount(response.count || items.length);
        setSearchContext(response.context || '');
        return;
      }

      const response = await api.listMemories({
        scope: scopeFilter === 'all' ? undefined : scopeFilter,
        assistant_id: assistantFilter || undefined,
        layer: layerFilter === 'all' ? undefined : layerFilter,
        include_inactive: showInactive,
        limit: maxLimit,
      });

      let items = response.items || [];
      if (trimmed) {
        const normalized = trimmed.toLowerCase();
        items = items.filter((item) => JSON.stringify(item).toLowerCase().includes(normalized));
      }
      setMemories(items);
      setResultCount(response.count || items.length);
      setSearchContext('');
    } catch (err) {
      setError(parseApiError(err, tr('memory.errors.loadList', 'Failed to load memories')));
      setMemories([]);
      setResultCount(0);
      setSearchContext('');
    } finally {
      setLoadingList(false);
    }
  }, [assistantFilter, clearStatus, layerFilter, limit, query, scopeFilter, showInactive, tr]);

  useEffect(() => {
    void loadBaseData();
  }, [loadBaseData]);

  useEffect(() => {
    if (!loadingPage) {
      void loadMemories();
    }
  }, [assistantFilter, layerFilter, limit, loadingPage, loadMemories, scopeFilter, showInactive]);

  const updateDraft = <K extends keyof MemorySettingsData>(key: K, value: MemorySettingsData[K]) => {
    setDraft((prev) => {
      if (!prev) return prev;
      return { ...prev, [key]: value };
    });
  };

  const toggleLayer = (layer: string, checked: boolean) => {
    setDraft((prev) => {
      if (!prev) return prev;
      const next = new Set(prev.enabled_layers);
      if (checked) next.add(layer);
      else next.delete(layer);
      return { ...prev, enabled_layers: Array.from(next) };
    });
  };

  const saveSettings = async () => {
    if (!draft) return;
    clearStatus();
    setSaving(true);
    try {
      const payload: MemorySettingsUpdate = {
        enabled: draft.enabled,
        profile_id: draft.profile_id,
        collection_name: draft.collection_name,
        enabled_layers: draft.enabled_layers,
        top_k: draft.top_k,
        score_threshold: draft.score_threshold,
        max_injected_items: draft.max_injected_items,
        max_item_length: draft.max_item_length,
        auto_extract_enabled: draft.auto_extract_enabled,
        min_text_length: draft.min_text_length,
        max_items_per_turn: draft.max_items_per_turn,
        global_enabled: draft.global_enabled,
        assistant_enabled: draft.assistant_enabled,
      };
      await api.updateMemorySettings(payload);
      const refreshed = await api.getMemorySettings();
      setDraft(refreshed);
      setMessage(tr('memory.messages.settingsUpdated', 'Memory settings updated'));
      void loadMemories();
    } catch (err) {
      setError(parseApiError(err, tr('memory.errors.saveSettings', 'Failed to save memory settings')));
    } finally {
      setSaving(false);
    }
  };

  const createMemory = async () => {
    clearStatus();
    if (!createForm.content.trim()) {
      setError(tr('memory.errors.contentRequired', 'Memory content is required'));
      return;
    }
    if (createForm.scope === 'assistant' && !createForm.assistant_id) {
      setError(tr('memory.errors.assistantRequired', 'Please select assistant for assistant scope'));
      return;
    }

    setCreating(true);
    try {
      await api.createMemory({
        ...createForm,
        content: createForm.content.trim(),
        profile_id: createForm.profile_id || draft?.profile_id,
      });
      setCreateForm({
        ...DEFAULT_CREATE_FORM,
        profile_id: createForm.profile_id || draft?.profile_id,
      });
      setMessage(tr('memory.messages.itemCreated', 'Memory item created'));
      void loadMemories();
    } catch (err) {
      setError(parseApiError(err, tr('memory.errors.createItem', 'Failed to create memory')));
    } finally {
      setCreating(false);
    }
  };

  const deleteMemory = async (item: MemoryItem) => {
    if (!window.confirm(tr('memory.messages.confirmDelete', 'Delete memory {{id}}?', { id: item.id }))) return;
    clearStatus();
    try {
      await api.deleteMemory(item.id);
      setMessage(tr('memory.messages.itemDeleted', 'Memory item deleted'));
      void loadMemories();
    } catch (err) {
      setError(parseApiError(err, tr('memory.errors.deleteItem', 'Failed to delete memory')));
    }
  };

  const toggleActive = async (item: MemoryItem) => {
    clearStatus();
    try {
      await api.updateMemory(item.id, { is_active: !(item.is_active ?? true) });
      setMessage(tr('memory.messages.statusUpdated', 'Memory status updated'));
      void loadMemories();
    } catch (err) {
      setError(parseApiError(err, tr('memory.errors.updateItem', 'Failed to update memory')));
    }
  };

  const togglePinned = async (item: MemoryItem) => {
    clearStatus();
    try {
      await api.updateMemory(item.id, { pinned: !item.pinned });
      setMessage(tr('memory.messages.pinUpdated', 'Memory pin status updated'));
      void loadMemories();
    } catch (err) {
      setError(parseApiError(err, tr('memory.errors.updateItem', 'Failed to update memory')));
    }
  };

  if (loadingPage || !draft) {
    return (
      <div className="space-y-4" data-name="memory-settings-loading">
        <PageHeader title={tr('memory.title', 'Memory')} description={tr('memory.loadingDescription', 'Loading memory settings...')} />
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-sm text-gray-600 dark:text-gray-300">
          {tr('memory.loading', 'Loading...')}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-name="memory-settings-page">
      <PageHeader
        title={(
          <span className="inline-flex items-center gap-2">
            <span>{tr('memory.title', 'Memory')}</span>
            <SettingsHelp
              help={{
                openTitle: tr('memory.help.openTitle', 'Open memory usage guide'),
                title: tr('memory.help.title', 'Memory Usage Guide'),
                size: 'xl',
                sections: [
                  {
                    title: tr('memory.help.quickStartTitle', 'Quick start'),
                    items: [
                      tr('memory.help.quickStartItem1', 'Turn on memory switches first, then save settings before creating new items.'),
                      tr('memory.help.quickStartItem2', 'Use global scope for long-term preferences, and assistant scope for role-specific instructions.'),
                      tr('memory.help.quickStartItem3', 'After applying filters, click Apply to refresh the visualization list from API results.'),
                    ],
                  },
                  {
                    title: tr('memory.help.pitfallsTitle', 'Common pitfalls'),
                    items: [
                      tr('memory.help.pitfallsItem1', 'If scope is assistant, assistant id is required. Missing assistant selection will fail create requests.'),
                      tr('memory.help.pitfallsItem2', 'Pinned only protects priority; inactive memories will still be excluded unless you reactivate them.'),
                      tr('memory.help.pitfallsItem3', 'Top K and threshold directly affect injection results. Too strict values can make memory look empty in chat.'),
                    ],
                  },
                ],
              }}
              triggerDataName="memory-help-trigger"
              contentDataName="memory-help-content"
            />
          </span>
        )}
        description={tr('memory.pageDescription', 'Settings toggles plus full memory visualization in one place.')}
        actions={(
          <button
            type="button"
            onClick={() => {
              void loadBaseData();
              void loadMemories();
            }}
            className="rounded-md border border-gray-300 dark:border-gray-600 px-3 py-1.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            {tr('memory.actions.refresh', 'Refresh')}
          </button>
        )}
      />

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/40 dark:text-red-300" data-name="memory-settings-error">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-md border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-700 dark:border-green-700 dark:bg-green-900/40 dark:text-green-300" data-name="memory-settings-success">
          {message}
        </div>
      )}

      <section className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-4" data-name="memory-settings-config">
        <h4 className="text-base font-semibold text-gray-900 dark:text-white">{tr('memory.sections.switches', 'Memory Switches')}</h4>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="flex items-center justify-between rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.enableMemory', 'Enable memory')}</span>
            <input type="checkbox" checked={draft.enabled} onChange={(event) => updateDraft('enabled', event.target.checked)} className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
          </label>
          <label className="flex items-center justify-between rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.enableGlobalScope', 'Enable global scope')}</span>
            <input type="checkbox" checked={draft.global_enabled} onChange={(event) => updateDraft('global_enabled', event.target.checked)} className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
          </label>
          <label className="flex items-center justify-between rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.enableAssistantScope', 'Enable assistant scope')}</span>
            <input type="checkbox" checked={draft.assistant_enabled} onChange={(event) => updateDraft('assistant_enabled', event.target.checked)} className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
          </label>
          <label className="flex items-center justify-between rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.enableAutoExtraction', 'Enable auto extraction')}</span>
            <input type="checkbox" checked={draft.auto_extract_enabled} onChange={(event) => updateDraft('auto_extract_enabled', event.target.checked)} className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-name="memory-settings-numbers">
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.profileId', 'Profile ID')}</span>
            <input className={fieldClassName} value={draft.profile_id} onChange={(event) => updateDraft('profile_id', event.target.value)} />
          </label>
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.collection', 'Collection')}</span>
            <input className={fieldClassName} value={draft.collection_name} onChange={(event) => updateDraft('collection_name', event.target.value)} />
          </label>
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.topK', 'Top K')}</span>
            <input type="number" min={1} max={30} className={fieldClassName} value={draft.top_k} onChange={(event) => updateDraft('top_k', Number(event.target.value))} />
          </label>
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.threshold', 'Threshold')}</span>
            <input type="number" min={0} max={1} step={0.01} className={fieldClassName} value={draft.score_threshold} onChange={(event) => updateDraft('score_threshold', Number(event.target.value))} />
          </label>
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.maxInjected', 'Max Injected')}</span>
            <input type="number" min={1} max={20} className={fieldClassName} value={draft.max_injected_items} onChange={(event) => updateDraft('max_injected_items', Number(event.target.value))} />
          </label>
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.maxItemLength', 'Max Item Length')}</span>
            <input type="number" min={50} max={800} className={fieldClassName} value={draft.max_item_length} onChange={(event) => updateDraft('max_item_length', Number(event.target.value))} />
          </label>
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.minTextLength', 'Min Text Length')}</span>
            <input type="number" min={1} max={200} className={fieldClassName} value={draft.min_text_length} onChange={(event) => updateDraft('min_text_length', Number(event.target.value))} />
          </label>
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.maxItemsPerTurn', 'Max Items Per Turn')}</span>
            <input type="number" min={1} max={20} className={fieldClassName} value={draft.max_items_per_turn} onChange={(event) => updateDraft('max_items_per_turn', Number(event.target.value))} />
          </label>
        </div>

        <div className="space-y-2" data-name="memory-settings-layers">
          <div className="text-sm font-medium text-gray-700 dark:text-gray-300">{tr('memory.fields.enabledLayers', 'Enabled Layers')}</div>
          <div className="flex flex-wrap gap-3">
            {LAYERS.map((layer) => (
              <label key={layer} className="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input type="checkbox" checked={draft.enabled_layers.includes(layer)} onChange={(event) => toggleLayer(layer, event.target.checked)} className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                {getLayerLabel(layer)}
              </label>
            ))}
          </div>
        </div>

        <button type="button" onClick={() => void saveSettings()} disabled={saving} className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">
          {saving ? tr('memory.actions.saving', 'Saving...') : tr('memory.actions.saveSettings', 'Save Settings')}
        </button>
      </section>

      <section className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3" data-name="memory-settings-create">
        <h4 className="text-base font-semibold text-gray-900 dark:text-white">{tr('memory.sections.createItem', 'Create Memory Item')}</h4>
        <textarea
          rows={3}
          value={createForm.content}
          onChange={(event) => setCreateForm((prev) => ({ ...prev, content: event.target.value }))}
          placeholder={tr('memory.placeholders.content', 'Full memory content')}
          className={fieldClassName}
        />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <select value={createForm.scope} onChange={(event) => setCreateForm((prev) => ({ ...prev, scope: event.target.value as MemoryScope }))} className={selectClassName}>
            <option value="global">{tr('memory.options.scopeGlobal', 'global')}</option>
            <option value="assistant">{tr('memory.options.scopeAssistant', 'assistant')}</option>
          </select>
          <select value={createForm.layer} onChange={(event) => setCreateForm((prev) => ({ ...prev, layer: event.target.value }))} className={selectClassName}>
            {LAYERS.map((layer) => <option key={layer} value={layer}>{getLayerLabel(layer)}</option>)}
          </select>
          <select value={createForm.assistant_id || ''} onChange={(event) => setCreateForm((prev) => ({ ...prev, assistant_id: event.target.value || undefined }))} disabled={createForm.scope !== 'assistant'} className={`${selectClassName} disabled:opacity-60 disabled:bg-gray-100 dark:disabled:bg-gray-800`}>
            <option value="">{tr('memory.options.assistant', 'assistant')}</option>
            {sortedAssistants.map((assistant) => <option key={assistant.id} value={assistant.id}>{assistant.name}</option>)}
          </select>
          <label className="inline-flex items-center gap-2 rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm text-gray-700 dark:text-gray-300">
            <input type="checkbox" checked={Boolean(createForm.pinned)} onChange={(event) => setCreateForm((prev) => ({ ...prev, pinned: event.target.checked }))} className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            {tr('memory.fields.pinned', 'Pinned')}
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.confidence', 'Confidence')}</span>
            <input type="number" min={0} max={1} step={0.01} value={createForm.confidence ?? 0.8} onChange={(event) => setCreateForm((prev) => ({ ...prev, confidence: Number(event.target.value) }))} className={fieldClassName} />
          </label>
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.importance', 'Importance')}</span>
            <input type="number" min={0} max={1} step={0.01} value={createForm.importance ?? 0.6} onChange={(event) => setCreateForm((prev) => ({ ...prev, importance: Number(event.target.value) }))} className={fieldClassName} />
          </label>
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.profileId', 'Profile ID')}</span>
            <input value={createForm.profile_id || ''} onChange={(event) => setCreateForm((prev) => ({ ...prev, profile_id: event.target.value || undefined }))} className={fieldClassName} />
          </label>
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.sessionSource', 'Session Source')}</span>
            <input value={createForm.source_session_id || ''} onChange={(event) => setCreateForm((prev) => ({ ...prev, source_session_id: event.target.value || undefined }))} className={fieldClassName} />
          </label>
          <label className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <span>{tr('memory.fields.messageSource', 'Message Source')}</span>
            <input value={createForm.source_message_id || ''} onChange={(event) => setCreateForm((prev) => ({ ...prev, source_message_id: event.target.value || undefined }))} className={fieldClassName} />
          </label>
        </div>

        <button type="button" onClick={() => void createMemory()} disabled={creating} className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">
          {creating ? tr('memory.actions.creating', 'Creating...') : tr('memory.actions.create', 'Create')}
        </button>
      </section>

      <section className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-4" data-name="memory-settings-visualization">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-base font-semibold text-gray-900 dark:text-white">{tr('memory.sections.visualization', 'Memory Visualization')}</h4>
          <span className="text-sm text-gray-500 dark:text-gray-400">{tr('memory.stats.visibleWithCount', 'Visible: {{visible}} / API Count: {{count}}', { visible: sortedMemories.length, count: resultCount })}</span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-6 gap-3" data-name="memory-settings-stats">
          <div className="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-700 dark:text-gray-300">{tr('memory.stats.total', 'Total')}: {stats.total}</div>
          <div className="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-300">{tr('memory.stats.active', 'Active')}: {stats.active}</div>
          <div className="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-amber-700 dark:text-amber-300">{tr('memory.stats.inactive', 'Inactive')}: {stats.inactive}</div>
          <div className="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-violet-700 dark:text-violet-300">{tr('memory.stats.pinned', 'Pinned')}: {stats.pinned}</div>
          <div className="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-700 dark:text-gray-300">{tr('memory.stats.global', 'Global')}: {stats.global}</div>
          <div className="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-700 dark:text-gray-300">{tr('memory.stats.assistant', 'Assistant')}: {stats.assistant}</div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-6 gap-3" data-name="memory-settings-filters">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void loadMemories();
            }}
            placeholder={tr('memory.placeholders.search', 'Search content / id / hash / metadata')}
            className={`md:col-span-2 ${fieldClassName}`}
          />
          <select value={scopeFilter} onChange={(event) => setScopeFilter(event.target.value as ScopeFilter)} className={selectClassName}>
            <option value="all">{tr('memory.options.allScopes', 'all scopes')}</option>
            <option value="global">{tr('memory.options.scopeGlobal', 'global')}</option>
            <option value="assistant">{tr('memory.options.scopeAssistant', 'assistant')}</option>
          </select>
          <select value={assistantFilter} onChange={(event) => setAssistantFilter(event.target.value)} className={selectClassName}>
            <option value="">{tr('memory.options.allAssistants', 'all assistants')}</option>
            {sortedAssistants.map((assistant) => <option key={assistant.id} value={assistant.id}>{assistant.name}</option>)}
          </select>
          <select value={layerFilter} onChange={(event) => setLayerFilter(event.target.value)} className={selectClassName}>
            <option value="all">{tr('memory.options.allLayers', 'all layers')}</option>
            {LAYERS.map((layer) => <option key={layer} value={layer}>{getLayerLabel(layer)}</option>)}
          </select>
          <select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)} className={selectClassName}>
            <option value="updated">{tr('memory.options.sortUpdated', 'updated desc')}</option>
            <option value="created">{tr('memory.options.sortCreated', 'created desc')}</option>
            <option value="score">{tr('memory.options.sortScore', 'score desc')}</option>
            <option value="importance">{tr('memory.options.sortImportance', 'importance desc')}</option>
            <option value="confidence">{tr('memory.options.sortConfidence', 'confidence desc')}</option>
            <option value="hit">{tr('memory.options.sortHit', 'hit count desc')}</option>
          </select>
          <div className="flex items-center gap-2">
            <input type="number" min={1} max={500} value={limit} onChange={(event) => setLimit(Number(event.target.value))} className={compactFieldClassName} />
            <button type="button" onClick={() => void loadMemories()} disabled={loadingList} className="rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-60">
              {loadingList ? tr('memory.actions.loading', 'Loading...') : tr('memory.actions.apply', 'Apply')}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4" data-name="memory-settings-advanced-options">
          <label className="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input type="checkbox" checked={showInactive} onChange={(event) => setShowInactive(event.target.checked)} className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            {tr('memory.fields.showInactive', 'Show inactive memories')}
          </label>
          <label className="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input type="checkbox" checked={showMetadataJson} onChange={(event) => setShowMetadataJson(event.target.checked)} className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            {tr('memory.fields.showMetadataJson', 'Show full metadata JSON')}
          </label>
        </div>

        {searchContext && (
          <div className="rounded-md border border-indigo-200 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-900/30 p-3" data-name="memory-settings-search-context">
            <div className="text-xs uppercase tracking-wide text-indigo-600 dark:text-indigo-300 mb-1">{tr('memory.sections.searchContext', 'Search Context')}</div>
            <pre className="whitespace-pre-wrap break-words text-xs text-indigo-900 dark:text-indigo-100">{searchContext}</pre>
          </div>
        )}

        <div className="space-y-3" data-name="memory-settings-list">
          {!loadingList && sortedMemories.length === 0 && (
            <div className="rounded-md border border-gray-200 dark:border-gray-700 p-3 text-sm text-gray-600 dark:text-gray-300">{tr('memory.empty', 'No memories found.')}</div>
          )}

          {sortedMemories.map((item) => {
            const assistantName = item.assistant_id ? (assistantNameMap[item.assistant_id] || item.assistant_id) : '-';

            return (
              <article key={item.id} className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3" data-name="memory-item-card">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-semibold text-gray-900 dark:text-white">{item.id}</span>
                    <span className="rounded bg-gray-100 dark:bg-gray-700 px-2 py-0.5 text-xs text-gray-700 dark:text-gray-200">{getScopeLabel(item.scope)}</span>
                    <span className="rounded bg-gray-100 dark:bg-gray-700 px-2 py-0.5 text-xs text-gray-700 dark:text-gray-200">{getLayerLabel(item.layer)}</span>
                    <span className={`rounded px-2 py-0.5 text-xs ${item.is_active === false ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'}`}>
                      {item.is_active === false ? tr('memory.badges.inactive', 'inactive') : tr('memory.badges.active', 'active')}
                    </span>
                    <span className={`rounded px-2 py-0.5 text-xs ${item.pinned ? 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300' : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200'}`}>
                      {item.pinned ? tr('memory.badges.pinned', 'pinned') : tr('memory.badges.notPinned', 'not pinned')}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button type="button" onClick={() => void togglePinned(item)} className="rounded-md border border-gray-300 dark:border-gray-600 px-2 py-1 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700">
                      {item.pinned ? tr('memory.actions.unpin', 'Unpin') : tr('memory.actions.pin', 'Pin')}
                    </button>
                    <button type="button" onClick={() => void toggleActive(item)} className="rounded-md border border-gray-300 dark:border-gray-600 px-2 py-1 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700">
                      {item.is_active === false ? tr('memory.actions.activate', 'Activate') : tr('memory.actions.deactivate', 'Deactivate')}
                    </button>
                    <button type="button" onClick={() => void deleteMemory(item)} className="rounded-md border border-red-300 dark:border-red-700 px-2 py-1 text-xs text-red-700 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/30">
                      {tr('memory.actions.delete', 'Delete')}
                    </button>
                  </div>
                </div>

                <div className="rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 p-3" data-name="memory-item-content">
                  <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">{tr('memory.fields.content', 'Content')}</div>
                  <pre className="whitespace-pre-wrap break-words font-sans text-sm text-gray-900 dark:text-gray-100">{item.content}</pre>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2 text-xs" data-name="memory-item-quick-metadata">
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.assistant', 'assistant')}: {assistantName}</div>
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.profileId', 'profile_id')}: {item.profile_id || '-'}</div>
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.score', 'score')}: {formatNum(item.score)}</div>
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.confidence', 'confidence')}: {formatNum(item.confidence)}</div>
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.importance', 'importance')}: {formatNum(item.importance)}</div>
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.hitCount', 'hit_count')}: {item.hit_count ?? 0}</div>
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.hash', 'hash')}: {item.hash || '-'}</div>
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.sourceSession', 'source_session')}: {item.source_session_id || '-'}</div>
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.sourceMessage', 'source_message')}: {item.source_message_id || '-'}</div>
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.createdAt', 'created_at')}: {formatDate(item.created_at)}</div>
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.updatedAt', 'updated_at')}: {formatDate(item.updated_at)}</div>
                  <div className="rounded border border-gray-200 dark:border-gray-700 px-2 py-1 text-gray-700 dark:text-gray-300">{tr('memory.meta.lastHitAt', 'last_hit_at')}: {formatDate(item.last_hit_at)}</div>
                </div>

                {showMetadataJson && (
                  <details open className="rounded-md border border-gray-200 dark:border-gray-700 p-2" data-name="memory-item-metadata">
                    <summary className="cursor-pointer text-sm text-gray-700 dark:text-gray-300">{tr('memory.sections.rawMetadata', 'Raw metadata JSON')}</summary>
                    <pre className="mt-2 whitespace-pre-wrap break-words text-xs text-gray-600 dark:text-gray-300">{JSON.stringify({
                      ...item,
                      created_at: formatDate(item.created_at),
                      updated_at: formatDate(item.updated_at),
                      last_hit_at: formatDate(item.last_hit_at),
                    }, null, 2)}</pre>
                  </details>
                )}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
};





