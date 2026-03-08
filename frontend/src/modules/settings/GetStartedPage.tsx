import React, { useDeferredValue, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CheckCircleIcon, RocketLaunchIcon, ServerStackIcon, SparklesIcon, WrenchScrewdriverIcon } from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { ErrorMessage, LoadingSpinner, PageHeader, SuccessMessage } from './components/common';
import { useAssistantSetupWizard } from './hooks/useAssistantSetupWizard';

const inputClassName = 'mt-2 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-200 dark:border-gray-600 dark:bg-gray-900 dark:text-white dark:focus:border-blue-400 dark:focus:ring-blue-900';
const textareaClassName = `${inputClassName} min-h-28 resize-y`;

const joinClasses = (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' ');

const resolutionTone: Record<string, string> = {
  created: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  updated: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  reused: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
};

export const GetStartedPage: React.FC = () => {
  const { t } = useTranslation('settings');
  const navigate = useNavigate();
  const wizard = useAssistantSetupWizard();
  const [moreProviderId, setMoreProviderId] = useState('');
  const [modelSearch, setModelSearch] = useState('');
  const deferredModelSearch = useDeferredValue(modelSearch);

  const filteredModels = useMemo(() => {
    const query = deferredModelSearch.trim().toLowerCase();
    if (!query) {
      return wizard.availableModels;
    }
    return wizard.availableModels.filter((model) => {
      const haystack = `${model.name || ''} ${model.id}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [deferredModelSearch, wizard.availableModels]);

  const stepItems = [
    t('wizard.step.chooseProvider'),
    t('wizard.step.connectProvider'),
    t('wizard.step.chooseModel'),
    t('wizard.step.createAssistant'),
  ];

  const summaryItems = [
    {
      key: 'provider',
      label: t('wizard.summary.provider'),
      value: wizard.providerDraft.name || wizard.providerDraft.id || t('wizard.summary.notConfigured'),
      subvalue: wizard.providerDraft.id || undefined,
      resolution: wizard.providerResolution,
    },
    {
      key: 'model',
      label: t('wizard.summary.model'),
      value: wizard.modelDraft.mode === 'catalog'
        ? (wizard.selectedModelInfo?.name || wizard.selectedModelInfo?.id || t('wizard.summary.notConfigured'))
        : (wizard.modelDraft.manualName || wizard.modelDraft.manualModelId || t('wizard.summary.notConfigured')),
      subvalue: wizard.resolvedModelId || undefined,
      resolution: wizard.modelResolution,
    },
    {
      key: 'assistant',
      label: t('wizard.summary.assistant'),
      value: wizard.assistantDraft.name || t('wizard.summary.notConfigured'),
      subvalue: wizard.assistantDraft.id || undefined,
      resolution: wizard.createdResources.assistantId ? 'created' : null,
    },
  ];

  const renderStepBar = () => (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/40" data-name="wizard-step-bar">
      <div className="mb-3 text-sm text-slate-600 dark:text-slate-300">{t('wizard.relationshipHint')}</div>
      <div className="grid gap-3 md:grid-cols-4">
        {stepItems.map((label, index) => {
          const stepNumber = index + 1;
          const isActive = wizard.step === stepNumber;
          const isDone = wizard.step > stepNumber;
          return (
            <div
              key={label}
              className={joinClasses(
                'rounded-xl border px-4 py-3 transition-colors',
                isDone && 'border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-900/20',
                isActive && 'border-blue-300 bg-white shadow-sm dark:border-blue-500 dark:bg-gray-800',
                !isDone && !isActive && 'border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-gray-900/40'
              )}
            >
              <div className="mb-2 flex items-center gap-2">
                <div className={joinClasses(
                  'flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold',
                  isDone && 'bg-emerald-600 text-white',
                  isActive && 'bg-blue-600 text-white',
                  !isDone && !isActive && 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
                )}>
                  {isDone ? <CheckCircleIcon className="h-5 w-5" /> : stepNumber}
                </div>
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
                  {t('wizard.stepLabel', { step: stepNumber })}
                </div>
              </div>
              <div className="text-sm font-medium text-slate-900 dark:text-white">{label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );

  const renderSummary = () => (
    <aside className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900/60" data-name="wizard-summary">
      <div className="mb-4 flex items-center gap-2">
        <SparklesIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
        <h4 className="text-base font-semibold text-gray-900 dark:text-white">{t('wizard.summary.title')}</h4>
      </div>
      <div className="space-y-4">
        {summaryItems.map((item) => (
          <div key={item.key} className="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
            <div className="mb-2 flex items-center justify-between gap-3">
              <div className="text-xs uppercase tracking-[0.2em] text-gray-500 dark:text-gray-400">{item.label}</div>
              {item.resolution && (
                <span className={joinClasses('rounded-full px-2.5 py-1 text-xs font-medium', resolutionTone[item.resolution])}>
                  {t(`wizard.resolution.${item.resolution}`)}
                </span>
              )}
            </div>
            <div className="text-sm font-medium text-gray-900 dark:text-white">{item.value}</div>
            {item.subvalue && (
              <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{item.subvalue}</div>
            )}
          </div>
        ))}
      </div>
      <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600 dark:bg-slate-800/70 dark:text-slate-300">
        {wizard.step < 5 ? t('wizard.summary.pendingNote') : t('wizard.summary.doneNote')}
      </div>
    </aside>
  );

  const renderProviderSelectionStep = () => (
    <section className="space-y-6" data-name="wizard-provider-selection-step">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {wizard.recommendedBuiltinProviders.map((provider) => {
          const selected = wizard.providerDraft.mode === 'builtin' && wizard.providerDraft.id === provider.id;
          const existing = wizard.providerDraft.id === provider.id ? wizard.existingProvider : null;
          return (
            <button
              key={provider.id}
              type="button"
              onClick={() => wizard.selectBuiltinProvider(provider)}
              data-name="wizard-provider-card"
              data-provider-id={provider.id}
              className={joinClasses(
                'rounded-2xl border p-5 text-left transition-all',
                selected
                  ? 'border-blue-500 bg-blue-50 shadow-sm dark:border-blue-400 dark:bg-blue-950/40'
                  : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/40 dark:border-gray-700 dark:bg-gray-900/60 dark:hover:border-blue-500 dark:hover:bg-gray-800'
              )}
            >
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <div className="text-base font-semibold text-gray-900 dark:text-white">{provider.name}</div>
                  <div className="text-xs uppercase tracking-[0.2em] text-gray-500 dark:text-gray-400">{provider.id}</div>
                </div>
                <ServerStackIcon className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-300">{provider.base_url}</div>
              <div className="mt-4 flex flex-wrap gap-2 text-xs">
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-gray-700 dark:bg-gray-800 dark:text-gray-300">{provider.protocol}</span>
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                  {provider.supports_model_list ? t('wizard.provider.supportsDiscovery') : t('wizard.provider.manualOnly')}
                </span>
                {existing && (
                  <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                    {t('wizard.provider.alreadyConfigured')}
                  </span>
                )}
              </div>
            </button>
          );
        })}

        <button
          type="button"
          onClick={() => wizard.selectCustomProvider()}
          data-name="wizard-provider-card-custom"
          className={joinClasses(
            'rounded-2xl border border-dashed p-5 text-left transition-all',
            wizard.providerDraft.mode === 'custom'
              ? 'border-blue-500 bg-blue-50 shadow-sm dark:border-blue-400 dark:bg-blue-950/40'
              : 'border-gray-300 bg-white hover:border-blue-300 hover:bg-blue-50/40 dark:border-gray-600 dark:bg-gray-900/60 dark:hover:border-blue-500 dark:hover:bg-gray-800'
          )}
        >
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-base font-semibold text-gray-900 dark:text-white">{t('wizard.provider.customTitle')}</div>
              <div className="text-sm text-gray-500 dark:text-gray-400">{t('wizard.provider.customDescription')}</div>
            </div>
            <WrenchScrewdriverIcon className="h-6 w-6 text-gray-600 dark:text-gray-300" />
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-300">{t('wizard.provider.customHint')}</div>
        </button>
      </div>

      {wizard.moreBuiltinProviders.length > 0 && (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-900/60">
          <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="more-provider-select">
            {t('wizard.provider.moreProviders')}
          </label>
          <div className="mt-3 flex flex-col gap-3 md:flex-row">
            <select
              id="more-provider-select"
              className={joinClasses(inputClassName, 'mt-0 md:max-w-md')}
              value={moreProviderId}
              onChange={(event) => {
                const nextId = event.target.value;
                setMoreProviderId(nextId);
                const builtin = wizard.moreBuiltinProviders.find((item) => item.id === nextId);
                if (builtin) {
                  wizard.selectBuiltinProvider(builtin);
                }
              }}
            >
              <option value="">{t('wizard.provider.selectMore')}</option>
              {wizard.moreBuiltinProviders.map((provider) => (
                <option key={provider.id} value={provider.id}>{provider.name} ({provider.id})</option>
              ))}
            </select>
            <div className="text-sm text-gray-500 dark:text-gray-400">{t('wizard.provider.moreProvidersHint')}</div>
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => wizard.goToProviderStep()}
          data-name="wizard-configure-provider"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
        >
          {t('wizard.action.configureProvider')}
        </button>
      </div>
    </section>
  );

  const renderProviderConfigStep = () => {
    const profileOptions = wizard.providerDraft.endpointProfiles || [];
    const showProfileSelect = wizard.providerDraft.mode === 'builtin' && profileOptions.length > 0;
    const showBaseUrlInput = !showProfileSelect || wizard.providerDraft.endpointProfileId === 'custom';

    return (
      <section className="space-y-6" data-name="wizard-provider-config-step">
        {wizard.existingProvider && (
          <SuccessMessage message={t('wizard.provider.existingNotice', { provider: wizard.existingProvider.name })} duration={0} />
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="provider-id">
              {t('wizard.field.providerId')}
            </label>
            <input
              id="provider-id"
              className={inputClassName}
              value={wizard.providerDraft.id}
              onChange={(event) => wizard.updateProviderDraft({ id: event.target.value })}
              disabled={wizard.providerDraft.mode === 'builtin'}
              placeholder={t('wizard.field.providerIdPlaceholder')}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="provider-name">
              {t('wizard.field.providerName')}
            </label>
            <input
              id="provider-name"
              className={inputClassName}
              value={wizard.providerDraft.name}
              onChange={(event) => wizard.updateProviderDraft({ name: event.target.value })}
              placeholder={t('wizard.field.providerNamePlaceholder')}
            />
          </div>

          {wizard.providerDraft.mode === 'custom' && (
            <div>
              <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="provider-protocol">
                {t('wizard.field.protocol')}
              </label>
              <select
                id="provider-protocol"
                className={inputClassName}
                value={wizard.providerDraft.protocol}
                onChange={(event) => wizard.updateProviderDraft({ protocol: event.target.value as typeof wizard.providerDraft.protocol })}
              >
                <option value="openai">{t('wizard.protocol.openai')}</option>
                <option value="anthropic">{t('wizard.protocol.anthropic')}</option>
                <option value="gemini">{t('wizard.protocol.gemini')}</option>
                <option value="ollama">{t('wizard.protocol.ollama')}</option>
                <option value="local_gguf">{t('wizard.protocol.localGguf')}</option>
              </select>
            </div>
          )}

          {showProfileSelect && (
            <div>
              <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="provider-endpoint-profile">
                {t('wizard.field.endpointProfile')}
              </label>
              <select
                id="provider-endpoint-profile"
                className={inputClassName}
                value={wizard.providerDraft.endpointProfileId || ''}
                onChange={(event) => wizard.updateProviderDraft({ endpointProfileId: event.target.value })}
              >
                {profileOptions.map((profile) => (
                  <option key={profile.id} value={profile.id}>{profile.label}</option>
                ))}
                <option value="custom">{t('wizard.field.customBaseUrl')}</option>
              </select>
            </div>
          )}

          <div className={joinClasses(showBaseUrlInput ? '' : 'lg:col-span-2')}>
            <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="provider-base-url">
              {t('wizard.field.baseUrl')}
            </label>
            <input
              id="provider-base-url"
              className={inputClassName}
              value={wizard.providerDraft.baseUrl}
              onChange={(event) => wizard.updateProviderDraft({ baseUrl: event.target.value })}
              placeholder={t('wizard.field.baseUrlPlaceholder')}
              readOnly={!showBaseUrlInput && showProfileSelect}
            />
            {!showBaseUrlInput && (
              <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">{t('wizard.field.baseUrlAutoHint')}</div>
            )}
          </div>

          <div className="lg:col-span-2">
            <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="provider-api-key">
              {t('wizard.field.apiKey')}
            </label>
            <input
              id="provider-api-key"
              type="password"
              className={inputClassName}
              value={wizard.providerDraft.apiKey}
              onChange={(event) => wizard.updateProviderDraft({ apiKey: event.target.value })}
              placeholder={t('wizard.field.apiKeyPlaceholder')}
            />
            <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              {wizard.existingProvider?.has_api_key
                ? t('wizard.field.apiKeyReuseHint')
                : t('wizard.field.apiKeyRequiredHint')}
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:justify-between">
          <button
            type="button"
            onClick={() => wizard.setStep(1)}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            {t('wizard.action.back')}
          </button>
          <button
            type="button"
            onClick={() => void wizard.submitProviderStep()}
            disabled={wizard.isSavingProvider}
            data-name="wizard-provider-next"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {wizard.isSavingProvider ? t('wizard.action.savingProvider') : t('wizard.action.toModels')}
          </button>
        </div>
      </section>
    );
  };

  const renderModelStep = () => (
    <section className="space-y-6" data-name="wizard-model-step">
      <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-900/60">
        <div className="mb-4 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-medium text-gray-900 dark:text-white">{t('wizard.model.providerReady', { provider: wizard.providerDraft.name || wizard.providerDraft.id })}</div>
            <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('wizard.model.discoveryHint')}</div>
          </div>
          <div className="flex gap-2">
            {wizard.availableModels.length > 0 && (
              <button
                type="button"
                onClick={() => wizard.updateModelDraft({ mode: 'catalog' })}
                className={joinClasses(
                  'rounded-lg px-3 py-2 text-sm font-medium transition',
                  wizard.modelDraft.mode === 'catalog'
                    ? 'bg-blue-600 text-white'
                    : 'border border-gray-300 text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800'
                )}
              >
                {t('wizard.model.pickFromList')}
              </button>
            )}
            <button
              type="button"
              onClick={() => wizard.updateModelDraft({ mode: 'manual' })}
              className={joinClasses(
                'rounded-lg px-3 py-2 text-sm font-medium transition',
                wizard.modelDraft.mode === 'manual'
                  ? 'bg-blue-600 text-white'
                  : 'border border-gray-300 text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800'
              )}
            >
              {t('wizard.model.manualEntry')}
            </button>
          </div>
        </div>

        {wizard.availableModelsError && (
          <div className="mb-4 space-y-3">
            <ErrorMessage message={t('wizard.error.fetchModels', { message: wizard.availableModelsError })} />
            <button
              type="button"
              onClick={() => void wizard.loadModels()}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
            >
              {t('wizard.action.retryModels')}
            </button>
          </div>
        )}

        {wizard.isFetchingModels && <LoadingSpinner message={t('wizard.loading.models')} size="sm" />}

        {wizard.modelDraft.mode === 'catalog' && wizard.availableModels.length > 0 && !wizard.isFetchingModels && (
          <div className="space-y-4">
            <input
              className={joinClasses(inputClassName, 'mt-0')}
              value={modelSearch}
              onChange={(event) => setModelSearch(event.target.value)}
              placeholder={t('wizard.model.searchPlaceholder')}
            />
            <div className="grid max-h-[26rem] gap-3 overflow-y-auto pr-1">
              {filteredModels.map((model) => {
                const selected = wizard.modelDraft.selectedModelId === model.id;
                const existing = wizard.existingModel?.id === model.id;
                return (
                  <button
                    key={model.id}
                    type="button"
                    onClick={() => wizard.updateModelDraft({ selectedModelId: model.id, manualModelId: model.id, manualName: model.name || model.id })}
                    data-name="wizard-model-option"
                    data-model-id={model.id}
                    className={joinClasses(
                      'rounded-xl border p-4 text-left transition',
                      selected
                        ? 'border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950/40'
                        : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/30 dark:border-gray-700 dark:bg-gray-900/50 dark:hover:border-blue-500 dark:hover:bg-gray-800'
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">{model.name || model.id}</div>
                        <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{model.id}</div>
                      </div>
                      {existing && (
                        <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                          {t('wizard.model.willReuse')}
                        </span>
                      )}
                    </div>
                    {Array.isArray(model.tags) && model.tags.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2 text-xs text-gray-600 dark:text-gray-300">
                        {model.tags.slice(0, 4).map((tag) => (
                          <span key={tag} className="rounded-full bg-gray-100 px-2 py-1 dark:bg-gray-800">{tag}</span>
                        ))}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
            {filteredModels.length === 0 && (
              <div className="rounded-xl border border-dashed border-gray-300 p-6 text-sm text-gray-500 dark:border-gray-600 dark:text-gray-400">
                {t('wizard.model.noSearchResults')}
              </div>
            )}
          </div>
        )}

        {(wizard.modelDraft.mode === 'manual' || (!wizard.isFetchingModels && wizard.availableModels.length === 0)) && (
          <div className="grid gap-5 lg:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="manual-model-id">
                {t('wizard.field.modelId')}
              </label>
              <input
                id="manual-model-id"
                className={inputClassName}
                value={wizard.modelDraft.manualModelId}
                onChange={(event) => wizard.updateModelDraft({ manualModelId: event.target.value })}
                placeholder={t('wizard.field.modelIdPlaceholder')}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="manual-model-name">
                {t('wizard.field.modelName')}
              </label>
              <input
                id="manual-model-name"
                className={inputClassName}
                value={wizard.modelDraft.manualName}
                onChange={(event) => wizard.updateModelDraft({ manualName: event.target.value })}
                placeholder={t('wizard.field.modelNamePlaceholder')}
              />
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:justify-between">
        <button
          type="button"
          onClick={() => wizard.setStep(2)}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          {t('wizard.action.back')}
        </button>
        <button
          type="button"
          onClick={() => void wizard.submitModelStep()}
          data-name="wizard-model-next"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
        >
          {t('wizard.action.toAssistant')}
        </button>
      </div>
    </section>
  );

  const renderAssistantStep = () => (
    <section className="space-y-6" data-name="wizard-assistant-step">
      <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-900/60">
        <div className="mb-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600 dark:bg-slate-800/70 dark:text-slate-300">
          {t('wizard.assistant.modelBinding', {
            model: wizard.resolvedModelId || t('wizard.summary.notConfigured'),
            provider: wizard.providerDraft.id || t('wizard.summary.notConfigured'),
          })}
        </div>
        <div className="grid gap-5 lg:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="assistant-id">
              {t('wizard.field.assistantId')}
            </label>
            <input
              id="assistant-id"
              className={inputClassName}
              value={wizard.assistantDraft.id}
              onChange={(event) => wizard.updateAssistantDraft({ id: event.target.value })}
              placeholder={t('wizard.field.assistantIdPlaceholder')}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="assistant-name">
              {t('wizard.field.assistantName')}
            </label>
            <input
              id="assistant-name"
              className={inputClassName}
              value={wizard.assistantDraft.name}
              onChange={(event) => wizard.updateAssistantDraft({ name: event.target.value })}
              placeholder={t('wizard.field.assistantNamePlaceholder')}
            />
          </div>
          <div className="lg:col-span-2">
            <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="assistant-description">
              {t('wizard.field.description')}
            </label>
            <input
              id="assistant-description"
              className={inputClassName}
              value={wizard.assistantDraft.description}
              onChange={(event) => wizard.updateAssistantDraft({ description: event.target.value })}
              placeholder={t('wizard.field.descriptionPlaceholder')}
            />
          </div>
          <div className="lg:col-span-2">
            <label className="block text-sm font-medium text-gray-900 dark:text-white" htmlFor="assistant-system-prompt">
              {t('wizard.field.systemPrompt')}
            </label>
            <textarea
              id="assistant-system-prompt"
              className={textareaClassName}
              value={wizard.assistantDraft.systemPrompt}
              onChange={(event) => wizard.updateAssistantDraft({ systemPrompt: event.target.value })}
              placeholder={t('wizard.field.systemPromptPlaceholder')}
            />
          </div>
          <label className="flex items-center gap-3 rounded-xl border border-gray-200 px-4 py-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200 lg:col-span-2">
            <input
              type="checkbox"
              checked={wizard.assistantDraft.enabled}
              onChange={(event) => wizard.updateAssistantDraft({ enabled: event.target.checked })}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600"
            />
            {t('wizard.field.enableAssistant')}
          </label>
        </div>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:justify-between">
        <button
          type="button"
          onClick={() => wizard.setStep(3)}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          {t('wizard.action.back')}
        </button>
        <button
          type="button"
          onClick={() => void wizard.submitAssistantStep()}
          disabled={wizard.isSubmittingAssistant}
          data-name="wizard-create-assistant"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {wizard.isSubmittingAssistant ? t('wizard.action.creatingAssistant') : t('wizard.action.createAssistant')}
        </button>
      </div>
    </section>
  );

  const renderDoneStep = () => (
    <section className="space-y-6" data-name="wizard-done-step">
      <div className="rounded-3xl border border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-blue-50 p-8 dark:border-emerald-900 dark:from-emerald-950/40 dark:via-gray-900 dark:to-blue-950/40">
        <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-600 text-white shadow-lg shadow-emerald-500/20">
          <RocketLaunchIcon className="h-7 w-7" />
        </div>
        <h4 className="text-2xl font-semibold text-gray-900 dark:text-white">{t('wizard.done.title')}</h4>
        <p className="mt-3 max-w-2xl text-sm text-gray-600 dark:text-gray-300">{t('wizard.done.description')}</p>
        <div className="mt-6 rounded-2xl bg-white/80 p-4 text-sm text-gray-600 shadow-sm dark:bg-gray-900/70 dark:text-gray-300">
          {t('wizard.done.defaultNote')}
        </div>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={() => navigate('/chat')}
            data-name="wizard-go-to-chat"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
          >
            {t('wizard.action.goToChat')}
          </button>
          {wizard.createdResources.assistantId && (
            <Link
              to={`/settings/assistants/${wizard.createdResources.assistantId}`}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
            >
              {t('wizard.action.viewAssistant')}
            </Link>
          )}
          <Link
            to="/settings/assistants"
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            {t('wizard.action.advancedSettings')}
          </Link>
          <button
            type="button"
            onClick={() => wizard.resetWizard()}
            className="rounded-lg border border-transparent px-4 py-2 text-sm font-medium text-blue-700 transition hover:bg-blue-50 dark:text-blue-300 dark:hover:bg-blue-950/40"
          >
            {t('wizard.action.createAnother')}
          </button>
        </div>
      </div>
    </section>
  );

  if (wizard.loadingConfig || wizard.loadingBuiltins) {
    return <LoadingSpinner message={t('wizard.loading.initial')} />;
  }

  if (wizard.loadingError) {
    return (
      <div className="space-y-6" data-name="wizard-load-error">
        <PageHeader title={t('wizard.title')} description={t('wizard.description')} />
        <ErrorMessage message={wizard.loadingError} />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-name="settings-get-started-page">
      <PageHeader
        title={t('wizard.title')}
        description={wizard.step === 5 ? t('wizard.done.description') : t('wizard.description')}
        actions={
          <Link
            to="/settings/assistants"
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            {t('wizard.action.skipToAdvanced')}
          </Link>
        }
      />

      {renderStepBar()}

      {wizard.builtinProvidersError && wizard.step === 1 && (
        <ErrorMessage message={t('wizard.error.loadBuiltins', { message: wizard.builtinProvidersError })} />
      )}

      {wizard.stepError && <ErrorMessage message={wizard.stepError} />}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          {wizard.step === 1 && renderProviderSelectionStep()}
          {wizard.step === 2 && renderProviderConfigStep()}
          {wizard.step === 3 && renderModelStep()}
          {wizard.step === 4 && renderAssistantStep()}
          {wizard.step === 5 && renderDoneStep()}
        </div>
        {renderSummary()}
      </div>
    </div>
  );
};
