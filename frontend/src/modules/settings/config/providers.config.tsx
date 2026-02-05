/**
 * Providers Page Configuration
 *
 * Defines the structure and behavior of the Providers settings page.
 * Note: This is a simplified version. Full features like test connection
 * and builtin provider picker can be added later.
 */

import type { CrudSettingsConfig } from './types';
import type { Provider } from '../../../types/model';

export const providersConfig: CrudSettingsConfig<Provider> = {
  type: 'crud',
  title: 'Provider List',
  description: 'Manage LLM providers (DeepSeek, OpenAI, Anthropic, etc.)',
  itemName: 'provider',
  itemNamePlural: 'providers',

  // Table configuration
  columns: [
    {
      key: 'name',
      label: 'Name',
      sortable: true,
      render: (_value, row) => (
        <div>
          <div className="text-sm font-medium text-gray-900 dark:text-white">
            {row.name}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {row.type === 'builtin' ? 'Builtin' : 'Custom'} - {row.protocol || 'openai'}
          </div>
        </div>
      )
    },
    {
      key: 'id',
      label: 'Provider ID',
      sortable: true,
      hideOnMobile: true
    },
    {
      key: 'api_key',
      label: 'API Key',
      hideOnMobile: true,
      render: (_value, row) => (
        <span className="text-gray-500 dark:text-gray-400">
          {row.has_api_key ? '••••••••' : 'Not set'}
        </span>
      )
    },
    {
      key: 'base_url',
      label: 'Base URL',
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
  searchPlaceholder: 'Search providers...',

  // Form fields
  createFields: [
    {
      type: 'text',
      name: 'id',
      label: 'Provider ID',
      placeholder: 'e.g., my-openai',
      required: true,
      helpText: 'Unique identifier for this provider'
    },
    {
      type: 'text',
      name: 'name',
      label: 'Display Name',
      placeholder: 'My OpenAI Provider',
      required: true
    },
    {
      type: 'select',
      name: 'protocol',
      label: 'API Protocol',
      required: true,
      defaultValue: 'openai',
      options: [
        { value: 'openai', label: 'OpenAI' },
        { value: 'anthropic', label: 'Anthropic' },
        { value: 'gemini', label: 'Google Gemini' },
        { value: 'ollama', label: 'Ollama' }
      ],
      helpText: 'API protocol used by this provider'
    },
    {
      type: 'text',
      name: 'base_url',
      label: 'Base URL',
      placeholder: 'https://api.openai.com/v1',
      required: true,
      helpText: 'API endpoint base URL'
    },
    {
      type: 'password',
      name: 'api_key',
      label: 'API Key',
      placeholder: 'sk-...',
      helpText: 'API key for authentication (leave empty to use environment variable)'
    },
    {
      type: 'text',
      name: 'api_key_env',
      label: 'API Key Env Var',
      placeholder: 'MY_PROVIDER_API_KEY',
      helpText: 'Environment variable name for API key'
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable this provider',
      defaultValue: true
    }
  ],

  editFields: [
    {
      type: 'text',
      name: 'id',
      label: 'Provider ID',
      required: true,
      disabled: true
    },
    {
      type: 'text',
      name: 'name',
      label: 'Display Name',
      placeholder: 'My OpenAI Provider',
      required: true
    },
    {
      type: 'select',
      name: 'protocol',
      label: 'API Protocol',
      required: true,
      options: [
        { value: 'openai', label: 'OpenAI' },
        { value: 'anthropic', label: 'Anthropic' },
        { value: 'gemini', label: 'Google Gemini' },
        { value: 'ollama', label: 'Ollama' }
      ],
      helpText: 'API protocol used by this provider'
    },
    {
      type: 'text',
      name: 'base_url',
      label: 'Base URL',
      placeholder: 'https://api.openai.com/v1',
      required: true,
      helpText: 'API endpoint base URL'
    },
    {
      type: 'password',
      name: 'api_key',
      label: 'API Key',
      placeholder: '••••••••',
      helpText: 'API key for authentication (leave unchanged if masked)'
    },
    {
      type: 'text',
      name: 'api_key_env',
      label: 'API Key Env Var',
      placeholder: 'MY_PROVIDER_API_KEY',
      helpText: 'Environment variable name for API key'
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable this provider',
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
