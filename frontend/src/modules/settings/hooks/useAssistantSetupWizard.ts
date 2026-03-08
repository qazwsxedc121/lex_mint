import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { AssistantCreate } from '../../../types/assistant';
import type {
  ApiProtocol,
  BuiltinProviderInfo,
  EndpointProfile,
  Model,
  ModelCapabilities,
  ModelInfo,
  Provider,
} from '../../../types/model';
import * as api from '../../../services/api';
import { useAssistants } from './useAssistants';
import { useModels } from './useModels';

export type WizardStep = 1 | 2 | 3 | 4 | 5;
export type ProviderMode = 'builtin' | 'custom';
export type ModelSelectionMode = 'catalog' | 'manual';
export type ResourceResolution = 'created' | 'updated' | 'reused' | null;

interface ProviderDraft {
  mode: ProviderMode;
  id: string;
  name: string;
  protocol: ApiProtocol;
  baseUrl: string;
  apiKey: string;
  endpointProfileId: string;
  type: Provider['type'];
  supportsModelList: boolean;
  defaultCapabilities?: ModelCapabilities;
  endpointProfiles: EndpointProfile[];
  sdkClass?: string;
}

interface ModelDraft {
  mode: ModelSelectionMode;
  selectedModelId: string;
  manualModelId: string;
  manualName: string;
}

interface AssistantDraft {
  id: string;
  name: string;
  description: string;
  systemPrompt: string;
  enabled: boolean;
}

interface CreatedResources {
  providerId: string | null;
  modelId: string | null;
  assistantId: string | null;
}

const RECOMMENDED_PROVIDER_IDS = ['openai', 'openrouter', 'anthropic', 'bailian', 'gemini', 'siliconflow'];
const CUSTOM_ENDPOINT_ID = 'custom';

const slugify = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-{2,}/g, '-');

const protocolRequiresApiKey = (protocol?: string) => !['ollama', 'local_gguf'].includes(protocol || '');

const toBuiltinDraft = (builtin: BuiltinProviderInfo, existing?: Provider): ProviderDraft => {
  const fallbackProfile = builtin.default_endpoint_profile_id || builtin.endpoint_profiles?.[0]?.id || '';
  const selectedProfile = builtin.endpoint_profiles?.find((profile) => profile.id === fallbackProfile);
  return {
    mode: 'builtin',
    id: builtin.id,
    name: existing?.name || builtin.name,
    protocol: (existing?.protocol || builtin.protocol || 'openai') as ApiProtocol,
    baseUrl: existing?.base_url || selectedProfile?.base_url || builtin.base_url || '',
    apiKey: '',
    endpointProfileId: existing?.endpoint_profile_id || fallbackProfile,
    type: 'builtin',
    supportsModelList: existing?.supports_model_list ?? builtin.supports_model_list,
    defaultCapabilities: builtin.default_capabilities,
    endpointProfiles: builtin.endpoint_profiles || [],
    sdkClass: builtin.sdk_class,
  };
};

const toCustomDraft = (): ProviderDraft => ({
  mode: 'custom',
  id: '',
  name: '',
  protocol: 'openai',
  baseUrl: '',
  apiKey: '',
  endpointProfileId: '',
  type: 'custom',
  supportsModelList: true,
  endpointProfiles: [],
});

const emptyModelDraft = (): ModelDraft => ({
  mode: 'catalog',
  selectedModelId: '',
  manualModelId: '',
  manualName: '',
});

const emptyAssistantDraft = (): AssistantDraft => ({
  id: '',
  name: '',
  description: '',
  systemPrompt: '',
  enabled: true,
});

const trimOrUndefined = (value: string) => {
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
};

export function useAssistantSetupWizard() {
  const { t } = useTranslation('settings');
  const modelsHook = useModels();
  const assistantsHook = useAssistants();
  const [step, setStep] = useState<WizardStep>(1);
  const [builtinProviders, setBuiltinProviders] = useState<BuiltinProviderInfo[]>([]);
  const [builtinProvidersError, setBuiltinProvidersError] = useState<string | null>(null);
  const [loadingBuiltins, setLoadingBuiltins] = useState(true);
  const [hasInitializedDefaultProvider, setHasInitializedDefaultProvider] = useState(false);
  const [providerDraft, setProviderDraft] = useState<ProviderDraft>(toCustomDraft());
  const [modelDraft, setModelDraft] = useState<ModelDraft>(emptyModelDraft());
  const [assistantDraft, setAssistantDraft] = useState<AssistantDraft>(emptyAssistantDraft());
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [availableModelsError, setAvailableModelsError] = useState<string | null>(null);
  const [isFetchingModels, setIsFetchingModels] = useState(false);
  const [stepError, setStepError] = useState<string | null>(null);
  const [isSavingProvider, setIsSavingProvider] = useState(false);
  const [isSubmittingAssistant, setIsSubmittingAssistant] = useState(false);
  const [providerResolution, setProviderResolution] = useState<ResourceResolution>(null);
  const [modelResolution, setModelResolution] = useState<ResourceResolution>(null);
  const [createdResources, setCreatedResources] = useState<CreatedResources>({
    providerId: null,
    modelId: null,
    assistantId: null,
  });

  useEffect(() => {
    let mounted = true;
    const loadBuiltins = async () => {
      setLoadingBuiltins(true);
      setBuiltinProvidersError(null);
      try {
        const data = await api.listBuiltinProviders();
        if (!mounted) {
          return;
        }
        setBuiltinProviders(data);
        if (data.length > 0 && !hasInitializedDefaultProvider) {
          const existing = modelsHook.providers.find((provider) => provider.id === data[0].id);
          setProviderDraft(toBuiltinDraft(data[0], existing));
          setHasInitializedDefaultProvider(true);
        }
      } catch (err) {
        if (!mounted) {
          return;
        }
        setBuiltinProvidersError(err instanceof Error ? err.message : t('wizard.runtime.loadBuiltinsFailed'));
        setProviderDraft(toCustomDraft());
      } finally {
        if (mounted) {
          setLoadingBuiltins(false);
        }
      }
    };
    void loadBuiltins();
    return () => {
      mounted = false;
    };
  }, [hasInitializedDefaultProvider, modelsHook.providers, t]);

  const selectedBuiltin = useMemo(
    () => builtinProviders.find((provider) => provider.id === providerDraft.id) || null,
    [builtinProviders, providerDraft.id]
  );

  const existingProvider = useMemo(
    () => modelsHook.providers.find((provider) => provider.id === providerDraft.id) || null,
    [modelsHook.providers, providerDraft.id]
  );

  const recommendedBuiltinProviders = useMemo(() => {
    const sorted = [...builtinProviders].sort((a, b) => {
      const aIndex = RECOMMENDED_PROVIDER_IDS.indexOf(a.id);
      const bIndex = RECOMMENDED_PROVIDER_IDS.indexOf(b.id);
      if (aIndex !== -1 || bIndex !== -1) {
        if (aIndex === -1) return 1;
        if (bIndex === -1) return -1;
        return aIndex - bIndex;
      }
      return a.name.localeCompare(b.name);
    });
    return sorted.slice(0, 6);
  }, [builtinProviders]);

  const moreBuiltinProviders = useMemo(() => {
    const recommendedIds = new Set(recommendedBuiltinProviders.map((provider) => provider.id));
    return builtinProviders
      .filter((provider) => !recommendedIds.has(provider.id))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [builtinProviders, recommendedBuiltinProviders]);

  const selectedModelInfo = useMemo(() => {
    if (!modelDraft.selectedModelId) {
      return null;
    }
    return availableModels.find((model) => model.id === modelDraft.selectedModelId) || null;
  }, [availableModels, modelDraft.selectedModelId]);

  const resolvedModelId = modelDraft.mode === 'catalog' ? modelDraft.selectedModelId : modelDraft.manualModelId.trim();
  const existingModel = useMemo(
    () => modelsHook.models.find((model) => model.provider_id === providerDraft.id && model.id === resolvedModelId) || null,
    [modelsHook.models, providerDraft.id, resolvedModelId]
  );

  const supportsModelList = providerDraft.supportsModelList;
  const needsApiKey = providerDraft.mode === 'builtin'
    ? protocolRequiresApiKey(providerDraft.protocol)
    : Boolean(providerDraft.apiKey.trim()) || protocolRequiresApiKey(providerDraft.protocol);

  const initializeAssistantDraft = (modelName: string, modelId: string) => {
    const nextName = assistantDraft.name.trim() || modelName || modelId;
    const nextId = assistantDraft.id.trim() || slugify(`${providerDraft.id}-${modelId}-assistant`);
    setAssistantDraft((current) => ({
      ...current,
      name: current.name.trim() || nextName,
      id: current.id.trim() || nextId,
    }));
  };

  const selectBuiltinProvider = (builtin: BuiltinProviderInfo) => {
    const existing = modelsHook.providers.find((provider) => provider.id === builtin.id);
    setProviderDraft(toBuiltinDraft(builtin, existing));
    setModelDraft(emptyModelDraft());
    setAssistantDraft(emptyAssistantDraft());
    setAvailableModels([]);
    setAvailableModelsError(null);
    setStepError(null);
    setProviderResolution(null);
    setModelResolution(null);
    setCreatedResources({ providerId: null, modelId: null, assistantId: null });
  };

  const selectCustomProvider = () => {
    setProviderDraft(toCustomDraft());
    setModelDraft((current) => ({ ...emptyModelDraft(), mode: current.mode }));
    setAssistantDraft(emptyAssistantDraft());
    setAvailableModels([]);
    setAvailableModelsError(null);
    setStepError(null);
    setProviderResolution(null);
    setModelResolution(null);
    setCreatedResources({ providerId: null, modelId: null, assistantId: null });
  };

  const updateProviderDraft = (patch: Partial<ProviderDraft>) => {
    setProviderDraft((current) => {
      const next = { ...current, ...patch };
      if (patch.endpointProfileId && patch.endpointProfileId !== CUSTOM_ENDPOINT_ID) {
        const selectedProfile = current.endpointProfiles.find((profile) => profile.id === patch.endpointProfileId);
        if (selectedProfile) {
          next.baseUrl = selectedProfile.base_url;
        }
      }
      return next;
    });
    setStepError(null);
  };

  const updateModelDraft = (patch: Partial<ModelDraft>) => {
    setModelDraft((current) => ({ ...current, ...patch }));
    setStepError(null);
  };

  const updateAssistantDraft = (patch: Partial<AssistantDraft>) => {
    setAssistantDraft((current) => ({ ...current, ...patch }));
    setStepError(null);
  };

  const buildProviderPayload = (): Provider => {
    const payload: Provider = {
      id: providerDraft.id.trim(),
      name: providerDraft.name.trim(),
      type: providerDraft.type,
      protocol: providerDraft.protocol,
      base_url: providerDraft.baseUrl.trim(),
      endpoint_profile_id: providerDraft.endpointProfileId && providerDraft.endpointProfileId !== CUSTOM_ENDPOINT_ID
        ? providerDraft.endpointProfileId
        : null,
      endpoint_profiles: providerDraft.endpointProfiles,
      enabled: true,
      supports_model_list: providerDraft.supportsModelList,
      default_capabilities: providerDraft.defaultCapabilities,
      sdk_class: providerDraft.sdkClass,
    };

    const apiKey = trimOrUndefined(providerDraft.apiKey);
    if (apiKey) {
      payload.api_key = apiKey;
    }
    return payload;
  };

  const ensureProvider = async () => {
    const providerId = providerDraft.id.trim();
    const name = providerDraft.name.trim();
    const baseUrl = providerDraft.baseUrl.trim();
    const hasExistingApiKey = existingProvider?.has_api_key === true;

    if (!providerId) {
      throw new Error(t('wizard.validation.providerIdRequired'));
    }
    if (!name) {
      throw new Error(t('wizard.validation.providerNameRequired'));
    }
    if (!baseUrl) {
      throw new Error(t('wizard.validation.baseUrlRequired'));
    }
    if (needsApiKey && !hasExistingApiKey && !providerDraft.apiKey.trim()) {
      throw new Error(t('wizard.validation.apiKeyRequired'));
    }

    const payload = buildProviderPayload();
    if (existingProvider) {
      await modelsHook.updateProvider(existingProvider.id, {
        ...existingProvider,
        ...payload,
      });
      setProviderResolution(payload.api_key || payload.base_url !== existingProvider.base_url || payload.name !== existingProvider.name ? 'updated' : 'reused');
      setCreatedResources((current) => ({ ...current, providerId: existingProvider.id }));
      return existingProvider.id;
    }

    await modelsHook.createProvider(payload);
    setProviderResolution('created');
    setCreatedResources((current) => ({ ...current, providerId: payload.id }));
    return payload.id;
  };

  const loadModels = async (providerId: string, forceMode?: ModelSelectionMode) => {
    if (!supportsModelList) {
      setAvailableModels([]);
      setAvailableModelsError(null);
      setModelDraft((current) => ({
        ...current,
        mode: 'manual',
        selectedModelId: '',
      }));
      return;
    }

    setIsFetchingModels(true);
    setAvailableModelsError(null);
    try {
      const fetchedModels = await api.fetchProviderModels(providerId);
      setAvailableModels(fetchedModels);
      setModelDraft((current) => {
        const nextMode = forceMode || (fetchedModels.length > 0 ? 'catalog' : 'manual');
        const defaultModelId = fetchedModels[0]?.id || '';
        const selectedModelId = current.selectedModelId && fetchedModels.some((model) => model.id === current.selectedModelId)
          ? current.selectedModelId
          : defaultModelId;
        return {
          ...current,
          mode: nextMode,
          selectedModelId,
          manualModelId: nextMode === 'manual' ? current.manualModelId : current.manualModelId,
          manualName: nextMode === 'manual' ? current.manualName : current.manualName,
        };
      });
    } catch (err) {
      setAvailableModels([]);
      setAvailableModelsError(err instanceof Error ? err.message : t('wizard.runtime.fetchModelsFailed'));
      setModelDraft((current) => ({ ...current, mode: 'manual', selectedModelId: '' }));
    } finally {
      setIsFetchingModels(false);
    }
  };

  const goToProviderStep = () => {
    setStep(2);
    setStepError(null);
  };

  const submitProviderStep = async () => {
    setIsSavingProvider(true);
    setStepError(null);
    try {
      const providerId = await ensureProvider();
      await loadModels(providerId);
      setStep(3);
    } catch (err) {
      setStepError(err instanceof Error ? err.message : t('wizard.runtime.saveProviderFailed'));
    } finally {
      setIsSavingProvider(false);
    }
  };

  const submitModelStep = async () => {
    const modelId = resolvedModelId.trim();
    if (!modelId) {
      setStepError(t('wizard.validation.modelRequired'));
      return;
    }
    const modelName = modelDraft.mode === 'catalog'
      ? selectedModelInfo?.name || modelId
      : modelDraft.manualName.trim() || modelId;
    initializeAssistantDraft(modelName, modelId);
    setStepError(null);
    setStep(4);
  };

  const ensureModel = async () => {
    const modelId = resolvedModelId.trim();
    if (!modelId) {
      throw new Error(t('wizard.validation.modelIdRequired'));
    }

    if (existingModel) {
      if (!existingModel.enabled) {
        await modelsHook.updateModel(`${existingModel.provider_id}:${existingModel.id}`, {
          ...existingModel,
          enabled: true,
        } as Model);
        setModelResolution('updated');
      } else {
        setModelResolution('reused');
      }
      setCreatedResources((current) => ({ ...current, modelId: `${existingModel.provider_id}:${existingModel.id}` }));
      return existingModel;
    }

    const selectedInfo = modelDraft.mode === 'catalog' ? selectedModelInfo : null;
    const payload: Model = {
      id: modelId,
      name: modelDraft.mode === 'catalog' ? selectedInfo?.name || modelId : modelDraft.manualName.trim() || modelId,
      provider_id: providerDraft.id,
      tags: selectedInfo?.tags || [],
      enabled: true,
      capabilities: selectedInfo?.capabilities,
    };
    await modelsHook.createModel(payload);
    setModelResolution('created');
    setCreatedResources((current) => ({ ...current, modelId: `${payload.provider_id}:${payload.id}` }));
    return payload;
  };

  const submitAssistantStep = async () => {
    const assistantId = assistantDraft.id.trim();
    const assistantName = assistantDraft.name.trim();
    if (!assistantId) {
      setStepError(t('wizard.validation.assistantIdRequired'));
      return;
    }
    if (!assistantName) {
      setStepError(t('wizard.validation.assistantNameRequired'));
      return;
    }
    if (assistantsHook.assistants.some((assistant) => assistant.id === assistantId)) {
      setStepError(t('wizard.validation.assistantIdExists'));
      return;
    }

    setIsSubmittingAssistant(true);
    setStepError(null);
    try {
      const model = await ensureModel();
      const payload: AssistantCreate = {
        id: assistantId,
        name: assistantName,
        description: trimOrUndefined(assistantDraft.description),
        model_id: `${model.provider_id}:${model.id}`,
        system_prompt: trimOrUndefined(assistantDraft.systemPrompt),
        enabled: assistantDraft.enabled,
        memory_enabled: false,
      };
      await assistantsHook.createAssistant(payload);
      setCreatedResources((current) => ({ ...current, assistantId }));
      setStep(5);
    } catch (err) {
      setStepError(err instanceof Error ? err.message : t('wizard.runtime.createAssistantFailed'));
    } finally {
      setIsSubmittingAssistant(false);
    }
  };

  const resetWizard = () => {
    if (recommendedBuiltinProviders.length > 0) {
      const nextBuiltin = recommendedBuiltinProviders[0];
      const existing = modelsHook.providers.find((provider) => provider.id === nextBuiltin.id);
      setProviderDraft(toBuiltinDraft(nextBuiltin, existing));
    } else {
      setProviderDraft(toCustomDraft());
    }
    setModelDraft(emptyModelDraft());
    setAssistantDraft(emptyAssistantDraft());
    setAvailableModels([]);
    setAvailableModelsError(null);
    setStepError(null);
    setProviderResolution(null);
    setModelResolution(null);
    setCreatedResources({ providerId: null, modelId: null, assistantId: null });
    setStep(1);
  };

  return {
    step,
    setStep,
    providerDraft,
    modelDraft,
    assistantDraft,
    builtinProviders,
    recommendedBuiltinProviders,
    moreBuiltinProviders,
    selectedBuiltin,
    existingProvider,
    existingModel,
    availableModels,
    availableModelsError,
    loadingBuiltins,
    builtinProvidersError,
    isFetchingModels,
    isSavingProvider,
    isSubmittingAssistant,
    loadingConfig: modelsHook.loading || assistantsHook.loading,
    loadingError: modelsHook.error || assistantsHook.error,
    stepError,
    providerResolution,
    modelResolution,
    createdResources,
    supportsModelList,
    resolvedModelId,
    selectedModelInfo,
    selectBuiltinProvider,
    selectCustomProvider,
    updateProviderDraft,
    updateModelDraft,
    updateAssistantDraft,
    goToProviderStep,
    submitProviderStep,
    submitModelStep,
    submitAssistantStep,
    loadModels: () => loadModels(providerDraft.id, modelDraft.mode),
    resetWizard,
  };
}
