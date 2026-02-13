/**
 * Providers Page Configuration
 *
 * Defines the structure and behavior of the Providers settings page.
 * Note: This is a simplified version. Full features like test connection
 * and builtin provider picker can be added later.
 */

import type { CrudSettingsConfig } from './types';
import type { Provider } from '../../../types/model';
import i18n from '../../../i18n';

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
            {row.type === 'builtin' ? i18n.t('settings:configField.builtin') : i18n.t('settings:configField.custom')} - {row.protocol || 'openai'}
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
      type: 'select',
      name: 'protocol',
      get label() { return i18n.t('settings:providers.field.protocol'); },
      required: true,
      defaultValue: 'openai',
      options: [
        { value: 'openai', label: 'OpenAI' },
        { value: 'anthropic', label: 'Anthropic' },
        { value: 'gemini', label: 'Google Gemini' },
        { value: 'ollama', label: 'Ollama' }
      ],
      get helpText() { return i18n.t('settings:providers.field.protocol.help'); }
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
      type: 'text',
      name: 'api_key_env',
      get label() { return i18n.t('settings:providers.field.apiKeyEnv'); },
      get placeholder() { return i18n.t('settings:providers.field.apiKeyEnv.placeholder'); },
      get helpText() { return i18n.t('settings:providers.field.apiKeyEnv.help'); }
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
      type: 'select',
      name: 'protocol',
      get label() { return i18n.t('settings:providers.field.protocol'); },
      required: true,
      options: [
        { value: 'openai', label: 'OpenAI' },
        { value: 'anthropic', label: 'Anthropic' },
        { value: 'gemini', label: 'Google Gemini' },
        { value: 'ollama', label: 'Ollama' }
      ],
      get helpText() { return i18n.t('settings:providers.field.protocol.help'); }
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
      type: 'text',
      name: 'api_key_env',
      get label() { return i18n.t('settings:providers.field.apiKeyEnv'); },
      get placeholder() { return i18n.t('settings:providers.field.apiKeyEnv.placeholder'); },
      get helpText() { return i18n.t('settings:providers.field.apiKeyEnv.help'); }
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
  }

  // TODO: Add custom actions for:
  // - Builtin provider picker
  // - Test connection
  // - Fetch available models
};
