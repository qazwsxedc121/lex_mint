/**
 * Providers Page Configuration
 *
 * Defines the structure and behavior of the Providers settings page.
 * Note: This is a simplified version. Full features like test connection
 * and builtin provider picker can be added later.
 */

import { SignalIcon } from '@heroicons/react/24/outline';
import type { CrudSettingsConfig } from './types';
import type { Provider } from '../../../types/model';
import { fetchProviderModels, testProviderStoredConnection } from '../../../services/api';
import i18n from '../../../i18n';

const BAILIAN_PROVIDER_ID = 'bailian';
const BAILIAN_DEFAULT_TEST_MODEL = 'qwen-plus';
const PROMPT_MODEL_PREVIEW_LIMIT = 12;
const SHOW_ADVANCED_FIELD = '__show_advanced';

const showAdvanced = (formData: Record<string, any>) => Boolean(formData?.[SHOW_ADVANCED_FIELD]);
const protocolLabel = (protocol?: string) =>
  i18n.t(`settings:providers.field.protocol.option.${protocol || 'openai'}`, {
    defaultValue: protocol || 'openai',
  });

async function pickBailianTestModel(provider: Provider): Promise<string | undefined | null> {
  try {
    const models = await fetchProviderModels(provider.id);
    const suggestedModel =
      models.find((model) => model.id === BAILIAN_DEFAULT_TEST_MODEL)?.id ||
      models[0]?.id ||
      BAILIAN_DEFAULT_TEST_MODEL;

    const previewLines = models
      .slice(0, PROMPT_MODEL_PREVIEW_LIMIT)
      .map((model, index) => `${index + 1}. ${model.id}`);
    const restCount = Math.max(models.length - PROMPT_MODEL_PREVIEW_LIMIT, 0);
    const tailLine = restCount > 0 ? `...and ${restCount} more` : '';

    const promptLines = [
      `Choose a model for ${provider.name} connection test.`,
      'Enter model id (leave empty to use suggested):',
      '',
      ...previewLines,
    ];
    if (tailLine) {
      promptLines.push(tailLine);
    }

    const input = window.prompt(promptLines.join('\n'), suggestedModel);
    if (input === null) {
      return null;
    }

    const trimmed = input.trim();
    return trimmed || suggestedModel;
  } catch {
    const input = window.prompt(
      `Enter model id for ${provider.name} connection test:`,
      BAILIAN_DEFAULT_TEST_MODEL
    );
    if (input === null) {
      return null;
    }
    const trimmed = input.trim();
    return trimmed || BAILIAN_DEFAULT_TEST_MODEL;
  }
}

export const providersConfig: CrudSettingsConfig<Provider> = {
  type: 'crud',
  get title() { return i18n.t('settings:providers.title'); },
  get description() { return i18n.t('settings:providers.description'); },
  get itemName() { return i18n.t('settings:providers.itemName'); },
  get itemNamePlural() { return i18n.t('settings:providers.itemNamePlural'); },
  createMode: 'page',
  createPath: '/settings/providers/new',
  editMode: 'page',
  editPath: (itemId) => `/settings/providers/${itemId}`,

  // Table configuration
  columns: [
    {
      key: 'name',
      get label() { return i18n.t('settings:providers.col.name'); },
      sortable: true,
      render: (_value, row) => (
        <div>
          <div className="text-sm font-medium text-gray-900 dark:text-white">
            {row.name}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {row.type === 'builtin' ? i18n.t('settings:configField.builtin') : i18n.t('settings:configField.custom')} - {protocolLabel(row.protocol)}
          </div>
        </div>
      )
    },
    {
      key: 'id',
      get label() { return i18n.t('settings:providers.col.providerId'); },
      sortable: true,
      hideOnMobile: true
    },
    {
      key: 'api_key',
      get label() { return i18n.t('settings:providers.col.apiKey'); },
      hideOnMobile: true,
      render: (_value, row) => (
        <span className="text-gray-500 dark:text-gray-400">
          {row.has_api_key ? '••••••••' : i18n.t('settings:configField.notSet')}
        </span>
      )
    },
    {
      key: 'base_url',
      get label() { return i18n.t('settings:providers.col.baseUrl'); },
      hideOnMobile: true,
      render: (value) => (
        <span className="text-xs font-mono text-gray-600 dark:text-gray-400">
          {value}
        </span>
      )
    }
  ],

  statusKey: 'enabled',

  enableSearch: true,
  get searchPlaceholder() { return i18n.t('settings:providers.search'); },

  // Form fields
  createFields: [
    {
      type: 'text',
      name: 'id',
      get label() { return i18n.t('settings:providers.field.id'); },
      get placeholder() { return i18n.t('settings:providers.field.id.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:providers.field.id.help'); }
    },
    {
      type: 'text',
      name: 'name',
      get label() { return i18n.t('settings:providers.field.name'); },
      get placeholder() { return i18n.t('settings:providers.field.name.placeholder'); },
      required: true
    },
    {
      type: 'checkbox',
      name: SHOW_ADVANCED_FIELD,
      get label() { return i18n.t('settings:providers.field.advanced'); },
      defaultValue: false,
      get helpText() { return i18n.t('settings:providers.field.advanced.help'); }
    },
    {
      type: 'select',
      name: 'protocol',
      get label() { return i18n.t('settings:providers.field.protocol'); },
      required: false,
      defaultValue: 'openai',
      options: [
        { value: 'openai', label: i18n.t('settings:providers.field.protocol.option.openai') },
        { value: 'anthropic', label: i18n.t('settings:providers.field.protocol.option.anthropic') },
        { value: 'gemini', label: i18n.t('settings:providers.field.protocol.option.gemini') },
        { value: 'ollama', label: i18n.t('settings:providers.field.protocol.option.ollama') }
      ],
      get helpText() { return i18n.t('settings:providers.field.protocol.help'); },
      condition: (formData) => showAdvanced(formData)
    },
    {
      type: 'select',
      name: 'call_mode',
      get label() { return i18n.t('settings:providers.field.callMode'); },
      required: false,
      defaultValue: 'auto',
      options: [
        { value: 'auto', label: i18n.t('settings:providers.field.callMode.option.auto') },
        { value: 'native', label: i18n.t('settings:providers.field.callMode.option.native') },
        { value: 'chat_completions', label: i18n.t('settings:providers.field.callMode.option.chatCompletions') },
        { value: 'responses', label: i18n.t('settings:providers.field.callMode.option.responses') }
      ],
      get helpText() { return i18n.t('settings:providers.field.callMode.help'); },
      condition: (formData) => showAdvanced(formData)
    },
    {
      type: 'text',
      name: 'base_url',
      get label() { return i18n.t('settings:providers.field.baseUrl'); },
      get placeholder() { return i18n.t('settings:providers.field.baseUrl.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:providers.field.baseUrl.help'); }
    },
    {
      type: 'password',
      name: 'api_key',
      get label() { return i18n.t('settings:providers.field.apiKey'); },
      get placeholder() { return i18n.t('settings:providers.field.apiKey.placeholder'); },
      get helpText() { return i18n.t('settings:providers.field.apiKey.help'); }
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:providers.field.enabled'); },
      defaultValue: true
    }
  ],

  editFields: [
    {
      type: 'text',
      name: 'id',
      get label() { return i18n.t('settings:providers.field.id'); },
      required: true,
      disabled: true
    },
    {
      type: 'text',
      name: 'name',
      get label() { return i18n.t('settings:providers.field.name'); },
      get placeholder() { return i18n.t('settings:providers.field.name.placeholder'); },
      required: true
    },
    {
      type: 'checkbox',
      name: SHOW_ADVANCED_FIELD,
      get label() { return i18n.t('settings:providers.field.advanced'); },
      defaultValue: false,
      get helpText() { return i18n.t('settings:providers.field.advanced.help'); }
    },
    {
      type: 'select',
      name: 'protocol',
      get label() { return i18n.t('settings:providers.field.protocol'); },
      required: false,
      options: [
        { value: 'openai', label: i18n.t('settings:providers.field.protocol.option.openai') },
        { value: 'anthropic', label: i18n.t('settings:providers.field.protocol.option.anthropic') },
        { value: 'gemini', label: i18n.t('settings:providers.field.protocol.option.gemini') },
        { value: 'ollama', label: i18n.t('settings:providers.field.protocol.option.ollama') }
      ],
      get helpText() { return i18n.t('settings:providers.field.protocol.help'); },
      condition: (formData) => showAdvanced(formData)
    },
    {
      type: 'select',
      name: 'call_mode',
      get label() { return i18n.t('settings:providers.field.callMode'); },
      required: false,
      defaultValue: 'auto',
      options: [
        { value: 'auto', label: i18n.t('settings:providers.field.callMode.option.auto') },
        { value: 'native', label: i18n.t('settings:providers.field.callMode.option.native') },
        { value: 'chat_completions', label: i18n.t('settings:providers.field.callMode.option.chatCompletions') },
        { value: 'responses', label: i18n.t('settings:providers.field.callMode.option.responses') }
      ],
      get helpText() { return i18n.t('settings:providers.field.callMode.help'); },
      condition: (formData) => showAdvanced(formData)
    },
    {
      type: 'text',
      name: 'base_url',
      get label() { return i18n.t('settings:providers.field.baseUrl'); },
      get placeholder() { return i18n.t('settings:providers.field.baseUrl.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:providers.field.baseUrl.help'); }
    },
    {
      type: 'password',
      name: 'api_key',
      get label() { return i18n.t('settings:providers.field.apiKey'); },
      placeholder: '••••••••',
      get helpText() { return i18n.t('settings:providers.field.apiKey.editHelp'); }
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:providers.field.enabled'); },
      defaultValue: true
    }
  ],

  // Enable default CRUD actions
  enableDefaultActions: {
    create: true,
    edit: true,
    delete: true,
    setDefault: false // Providers don't have a default
  },

  // Built-in providers are preloaded and should not be deleted in UI.
  defaultActionVisibility: {
    delete: (item) => item.type !== 'builtin'
  },

  // Row actions
  rowActions: [
    {
      id: 'test-connection',
      label: '',
      icon: SignalIcon,
      get tooltip() { return i18n.t('settings:providers.action.testConnection'); },
      disabled: (item: Provider) => {
        const requiresApiKey = item.requires_api_key !== false;
        return requiresApiKey && !item.has_api_key;
      },
      onClick: async (item: Provider) => {
        try {
          let selectedModelId: string | undefined;
          if (item.id === BAILIAN_PROVIDER_ID) {
            const pickedModel = await pickBailianTestModel(item);
            if (pickedModel === null) {
              return;
            }
            selectedModelId = pickedModel;
          }

          const result = await testProviderStoredConnection(item.id, item.base_url, selectedModelId);
          if (result.success) {
            alert(i18n.t('settings:testConnection.success') + '\n' + result.message);
          } else {
            alert(i18n.t('settings:testConnection.failed') + '\n' + result.message);
          }
        } catch (err: any) {
          alert(i18n.t('settings:testConnection.failed') + '\n' + (err.message || String(err)));
        }
      }
    }
  ]

  // TODO: Add custom actions for:
  // - Builtin provider picker
  // - Fetch available models
};
