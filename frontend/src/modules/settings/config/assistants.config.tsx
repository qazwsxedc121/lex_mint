/**
 * Assistants Page Configuration
 *
 * Defines the structure and behavior of the Assistants settings page.
 */

import type { CrudSettingsConfig } from './types';
import type { Assistant } from '../../../types/assistant';
import { PARAM_SUPPORT } from '../../../shared/constants/paramSupport';
import { getAssistantIcon } from '../../../shared/constants/assistantIcons';

// === Provider-aware parameter visibility ===

const getProviderId = (formData: any): string | undefined => {
  const modelId = formData.model_id;
  if (!modelId) return undefined;
  const parts = String(modelId).split(':');
  return parts.length ? parts[0] : undefined;
};

const getSdkClass = (formData: any, context: any): string => {
  const providerId = getProviderId(formData);
  const provider = context.providers?.find((p: any) => p.id === providerId);
  return provider?.sdk_class || provider?.protocol || 'openai';
};

const supportsParam = (param: string) => (formData: any, context: any): boolean => {
  if (!formData.model_id) return false;
  const sdk = getSdkClass(formData, context);
  return (PARAM_SUPPORT[param] || []).includes(sdk);
};

// === Shared field definitions for LLM parameters ===

const llmParamFields = [
  {
    type: 'slider' as const,
    name: 'max_tokens',
    label: 'Max Tokens',
    min: 1,
    max: 8192,
    step: 1,
    defaultValue: 1024,
    allowEmpty: true,
    emptyLabel: 'Default',
    showValue: true,
    formatValue: (v: number) => Math.round(v).toString(),
    helpText: 'Max output tokens (empty = provider default)',
    condition: supportsParam('max_tokens'),
  },
  {
    type: 'slider' as const,
    name: 'top_p',
    label: 'Top P',
    min: 0,
    max: 1,
    step: 0.05,
    defaultValue: 1,
    allowEmpty: true,
    emptyLabel: 'Default',
    showValue: true,
    formatValue: (v: number) => v.toFixed(2),
    helpText: 'Top-p nucleus sampling (empty = provider default)',
    condition: supportsParam('top_p'),
  },
  {
    type: 'slider' as const,
    name: 'top_k',
    label: 'Top K',
    min: 1,
    max: 200,
    step: 1,
    defaultValue: 40,
    allowEmpty: true,
    emptyLabel: 'Default',
    showValue: true,
    formatValue: (v: number) => Math.round(v).toString(),
    helpText: 'Top-k sampling (empty = provider default)',
    condition: supportsParam('top_k'),
  },
  {
    type: 'slider' as const,
    name: 'frequency_penalty',
    label: 'Frequency Penalty',
    min: -2,
    max: 2,
    step: 0.1,
    defaultValue: 0,
    allowEmpty: true,
    emptyLabel: 'Default',
    showValue: true,
    formatValue: (v: number) => v.toFixed(1),
    helpText: 'Frequency penalty (empty = provider default)',
    condition: supportsParam('frequency_penalty'),
  },
  {
    type: 'slider' as const,
    name: 'presence_penalty',
    label: 'Presence Penalty',
    min: -2,
    max: 2,
    step: 0.1,
    defaultValue: 0,
    allowEmpty: true,
    emptyLabel: 'Default',
    showValue: true,
    formatValue: (v: number) => v.toFixed(1),
    helpText: 'Presence penalty (empty = provider default)',
    condition: supportsParam('presence_penalty'),
  },
];

export const assistantsConfig: CrudSettingsConfig<Assistant> = {
  type: 'crud',
  title: 'Assistant List',
  description: 'Configure assistants with models, temperatures, and sampling parameters',
  itemName: 'assistant',
  itemNamePlural: 'assistants',
  createMode: 'page',
  createPath: '/settings/assistants/new',
  editMode: 'page',
  editPath: (itemId) => `/settings/assistants/${itemId}`,

  // Table configuration
  columns: [
    {
      key: 'icon',
      label: '',
      width: 'w-12',
      render: (_value, row) => {
        const Icon = getAssistantIcon(row.icon);
        return (
          <div className="flex items-center justify-center">
            <Icon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </div>
        );
      }
    },
    {
      key: 'name',
      label: 'Name',
      sortable: true,
      render: (_value, row) => (
        <div>
          <div className="text-sm font-medium text-gray-900 dark:text-white">
            {row.name}
          </div>
          {row.description && (
            <div className="text-xs text-gray-500 dark:text-gray-400">
              {row.description}
            </div>
          )}
        </div>
      )
    },
    {
      key: 'model_id',
      label: 'Model',
      sortable: true,
      hideOnMobile: true
    },
    {
      key: 'temperature',
      label: 'Temperature',
      sortable: true,
      hideOnMobile: true,
      render: (value) => value ?? 0.7
    },
    {
      key: 'max_rounds',
      label: 'Max Rounds',
      sortable: true,
      hideOnMobile: true,
      render: (value) => {
        if (value === -1 || value === null || value === undefined) {
          return 'Unlimited';
        }
        return value;
      }
    },
    {
      key: 'memory_enabled',
      label: 'Memory',
      sortable: true,
      hideOnMobile: true,
      render: (value) => (value === true ? 'On' : 'Off')
    }
  ],

  statusKey: 'enabled',
  defaultKey: undefined, // Will use defaultItemId from hook

  enableSearch: true,
  searchPlaceholder: 'Search assistants...',

  // Form fields for create
  createFields: [
    {
      type: 'text',
      name: 'id',
      label: 'Assistant ID',
      placeholder: 'e.g., my-assistant',
      required: true,
      helpText: 'Unique identifier for this assistant'
    },
    {
      type: 'text',
      name: 'name',
      label: 'Name',
      placeholder: 'My Assistant',
      required: true
    },
    {
      type: 'icon-picker' as const,
      name: 'icon',
      label: 'Icon',
      helpText: 'Choose an icon for this assistant'
    },
    {
      type: 'text',
      name: 'description',
      label: 'Description',
      placeholder: 'Optional description',
      helpText: 'Brief description of this assistant'
    },
    {
      type: 'select',
      name: 'model_id',
      label: 'Model',
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models
          .filter((m: any) => m.enabled)
          .map((m: any) => ({
            value: `${m.provider_id}:${m.id}`,
            label: `${m.name} (${m.provider_id}:${m.id})`
          }));
      },
      helpText: 'Language model to use for this assistant'
    },
    {
      type: 'textarea',
      name: 'system_prompt',
      label: 'System Prompt',
      placeholder: 'Optional system prompt...',
      rows: 3,
      helpText: 'Custom instructions for the assistant'
    },
    {
      type: 'slider',
      name: 'temperature',
      label: 'Temperature',
      min: 0,
      max: 2,
      step: 0.1,
      defaultValue: 0.7,
      showValue: true,
      showLabels: true,
      minLabel: '0.0 (Precise)',
      maxLabel: '2.0 (Creative)',
      formatValue: (v) => v.toFixed(1),
      helpText: 'Controls randomness in responses'
    },
    ...llmParamFields,
    {
      type: 'number',
      name: 'max_rounds',
      label: 'Max Rounds',
      placeholder: '-1 for unlimited',
      min: -1,
      helpText: '-1 or empty = unlimited conversation rounds'
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable this assistant',
      defaultValue: true
    },
    {
      type: 'checkbox',
      name: 'memory_enabled',
      label: 'Enable assistant memory',
      defaultValue: false
    },
    {
      type: 'multi-select' as const,
      name: 'knowledge_base_ids',
      label: 'Knowledge Bases',
      defaultValue: [],
      dynamicOptions: (context: any) => {
        const kbs = context.knowledgeBases || [];
        return kbs
          .filter((kb: any) => kb.enabled)
          .map((kb: any) => ({
            value: kb.id,
            label: `${kb.name}${kb.description ? ` - ${kb.description}` : ''}`,
          }));
      },
      helpText: 'Select knowledge bases to use for RAG with this assistant'
    }
  ],

  // Edit fields (id is disabled)
  editFields: [
    {
      type: 'text',
      name: 'id',
      label: 'Assistant ID',
      required: true,
      disabled: true
    },
    {
      type: 'text',
      name: 'name',
      label: 'Name',
      placeholder: 'My Assistant',
      required: true
    },
    {
      type: 'icon-picker' as const,
      name: 'icon',
      label: 'Icon',
      helpText: 'Choose an icon for this assistant'
    },
    {
      type: 'text',
      name: 'description',
      label: 'Description',
      placeholder: 'Optional description',
      helpText: 'Brief description of this assistant'
    },
    {
      type: 'select',
      name: 'model_id',
      label: 'Model',
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models
          .filter((m: any) => m.enabled)
          .map((m: any) => ({
            value: `${m.provider_id}:${m.id}`,
            label: `${m.name} (${m.provider_id}:${m.id})`
          }));
      },
      helpText: 'Language model to use for this assistant'
    },
    {
      type: 'textarea',
      name: 'system_prompt',
      label: 'System Prompt',
      placeholder: 'Optional system prompt...',
      rows: 3,
      helpText: 'Custom instructions for the assistant'
    },
    {
      type: 'slider',
      name: 'temperature',
      label: 'Temperature',
      min: 0,
      max: 2,
      step: 0.1,
      defaultValue: 0.7,
      showValue: true,
      showLabels: true,
      minLabel: '0.0 (Precise)',
      maxLabel: '2.0 (Creative)',
      formatValue: (v) => v.toFixed(1),
      helpText: 'Controls randomness in responses'
    },
    ...llmParamFields,
    {
      type: 'number',
      name: 'max_rounds',
      label: 'Max Rounds',
      placeholder: '-1 for unlimited',
      min: -1,
      helpText: '-1 or empty = unlimited conversation rounds'
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable this assistant',
      defaultValue: true
    },
    {
      type: 'checkbox',
      name: 'memory_enabled',
      label: 'Enable assistant memory',
      defaultValue: false
    },
    {
      type: 'multi-select' as const,
      name: 'knowledge_base_ids',
      label: 'Knowledge Bases',
      defaultValue: [],
      dynamicOptions: (context: any) => {
        const kbs = context.knowledgeBases || [];
        return kbs
          .filter((kb: any) => kb.enabled)
          .map((kb: any) => ({
            value: kb.id,
            label: `${kb.name}${kb.description ? ` - ${kb.description}` : ''}`,
          }));
      },
      helpText: 'Select knowledge bases to use for RAG with this assistant'
    }
  ],

  // Enable default CRUD actions
  enableDefaultActions: {
    create: true,
    edit: true,
    delete: true,
    setDefault: true
  }
};
