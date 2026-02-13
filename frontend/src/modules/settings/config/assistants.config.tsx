/**
 * Assistants Page Configuration
 *
 * Defines the structure and behavior of the Assistants settings page.
 */

import type { CrudSettingsConfig } from './types';
import type { Assistant } from '../../../types/assistant';
import { PARAM_SUPPORT } from '../../../shared/constants/paramSupport';
import { getAssistantIcon } from '../../../shared/constants/assistantIcons';
import i18n from '../../../i18n';

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
    get label() { return i18n.t('settings:assistants.field.maxTokens'); },
    min: 1,
    max: 8192,
    step: 1,
    defaultValue: 1024,
    allowEmpty: true,
    get emptyLabel() { return i18n.t('common:default'); },
    showValue: true,
    formatValue: (v: number) => Math.round(v).toString(),
    get helpText() { return i18n.t('settings:assistants.field.maxTokens.help'); },
    condition: supportsParam('max_tokens'),
  },
  {
    type: 'slider' as const,
    name: 'top_p',
    get label() { return i18n.t('settings:assistants.field.topP'); },
    min: 0,
    max: 1,
    step: 0.05,
    defaultValue: 1,
    allowEmpty: true,
    get emptyLabel() { return i18n.t('common:default'); },
    showValue: true,
    formatValue: (v: number) => v.toFixed(2),
    get helpText() { return i18n.t('settings:assistants.field.topP.help'); },
    condition: supportsParam('top_p'),
  },
  {
    type: 'slider' as const,
    name: 'top_k',
    get label() { return i18n.t('settings:assistants.field.topK'); },
    min: 1,
    max: 200,
    step: 1,
    defaultValue: 40,
    allowEmpty: true,
    get emptyLabel() { return i18n.t('common:default'); },
    showValue: true,
    formatValue: (v: number) => Math.round(v).toString(),
    get helpText() { return i18n.t('settings:assistants.field.topK.help'); },
    condition: supportsParam('top_k'),
  },
  {
    type: 'slider' as const,
    name: 'frequency_penalty',
    get label() { return i18n.t('settings:assistants.field.frequencyPenalty'); },
    min: -2,
    max: 2,
    step: 0.1,
    defaultValue: 0,
    allowEmpty: true,
    get emptyLabel() { return i18n.t('common:default'); },
    showValue: true,
    formatValue: (v: number) => v.toFixed(1),
    get helpText() { return i18n.t('settings:assistants.field.frequencyPenalty.help'); },
    condition: supportsParam('frequency_penalty'),
  },
  {
    type: 'slider' as const,
    name: 'presence_penalty',
    get label() { return i18n.t('settings:assistants.field.presencePenalty'); },
    min: -2,
    max: 2,
    step: 0.1,
    defaultValue: 0,
    allowEmpty: true,
    get emptyLabel() { return i18n.t('common:default'); },
    showValue: true,
    formatValue: (v: number) => v.toFixed(1),
    get helpText() { return i18n.t('settings:assistants.field.presencePenalty.help'); },
    condition: supportsParam('presence_penalty'),
  },
];

export const assistantsConfig: CrudSettingsConfig<Assistant> = {
  type: 'crud',
  get title() { return i18n.t('settings:assistants.title'); },
  get description() { return i18n.t('settings:assistants.description'); },
  get itemName() { return i18n.t('settings:assistants.itemName'); },
  get itemNamePlural() { return i18n.t('settings:assistants.itemNamePlural'); },
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
      get label() { return i18n.t('settings:assistants.col.name'); },
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
      get label() { return i18n.t('settings:assistants.col.model'); },
      sortable: true,
      hideOnMobile: true
    },
    {
      key: 'temperature',
      get label() { return i18n.t('settings:assistants.col.temperature'); },
      sortable: true,
      hideOnMobile: true,
      render: (value) => value ?? 0.7
    },
    {
      key: 'max_rounds',
      get label() { return i18n.t('settings:assistants.col.maxRounds'); },
      sortable: true,
      hideOnMobile: true,
      render: (value) => {
        if (value === -1 || value === null || value === undefined) {
          return i18n.t('settings:configField.unlimited');
        }
        return value;
      }
    },
    {
      key: 'memory_enabled',
      get label() { return i18n.t('settings:assistants.col.memory'); },
      sortable: true,
      hideOnMobile: true,
      render: (value) => (value === true ? i18n.t('settings:configField.on') : i18n.t('settings:configField.off'))
    }
  ],

  statusKey: 'enabled',
  defaultKey: undefined, // Will use defaultItemId from hook

  enableSearch: true,
  get searchPlaceholder() { return i18n.t('settings:assistants.search'); },

  // Form fields for create
  createFields: [
    {
      type: 'text',
      name: 'id',
      get label() { return i18n.t('settings:assistants.field.id'); },
      get placeholder() { return i18n.t('settings:assistants.field.id.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:assistants.field.id.help'); }
    },
    {
      type: 'text',
      name: 'name',
      get label() { return i18n.t('settings:assistants.field.name'); },
      get placeholder() { return i18n.t('settings:assistants.field.name.placeholder'); },
      required: true
    },
    {
      type: 'icon-picker' as const,
      name: 'icon',
      get label() { return i18n.t('settings:assistants.field.icon'); },
      get helpText() { return i18n.t('settings:assistants.field.icon.help'); }
    },
    {
      type: 'text',
      name: 'description',
      get label() { return i18n.t('settings:assistants.field.description'); },
      get placeholder() { return i18n.t('settings:assistants.field.description.placeholder'); },
      get helpText() { return i18n.t('settings:assistants.field.description.help'); }
    },
    {
      type: 'select',
      name: 'model_id',
      get label() { return i18n.t('settings:assistants.field.modelId'); },
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
      get helpText() { return i18n.t('settings:assistants.field.modelId.help'); }
    },
    {
      type: 'textarea',
      name: 'system_prompt',
      get label() { return i18n.t('settings:assistants.field.systemPrompt'); },
      get placeholder() { return i18n.t('settings:assistants.field.systemPrompt.placeholder'); },
      rows: 3,
      get helpText() { return i18n.t('settings:assistants.field.systemPrompt.help'); }
    },
    {
      type: 'slider',
      name: 'temperature',
      get label() { return i18n.t('settings:assistants.field.temperature'); },
      min: 0,
      max: 2,
      step: 0.1,
      defaultValue: 0.7,
      showValue: true,
      showLabels: true,
      get minLabel() { return i18n.t('settings:assistants.field.temperature.minLabel'); },
      get maxLabel() { return i18n.t('settings:assistants.field.temperature.maxLabel'); },
      formatValue: (v) => v.toFixed(1),
      get helpText() { return i18n.t('settings:assistants.field.temperature.help'); }
    },
    ...llmParamFields,
    {
      type: 'number',
      name: 'max_rounds',
      get label() { return i18n.t('settings:assistants.field.maxRounds'); },
      get placeholder() { return i18n.t('settings:assistants.field.maxRounds.placeholder'); },
      min: -1,
      get helpText() { return i18n.t('settings:assistants.field.maxRounds.help'); }
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:assistants.field.enabled'); },
      defaultValue: true
    },
    {
      type: 'checkbox',
      name: 'memory_enabled',
      get label() { return i18n.t('settings:assistants.field.memoryEnabled'); },
      defaultValue: false
    },
    {
      type: 'multi-select' as const,
      name: 'knowledge_base_ids',
      get label() { return i18n.t('settings:assistants.field.knowledgeBases'); },
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
      get helpText() { return i18n.t('settings:assistants.field.knowledgeBases.help'); }
    }
  ],

  // Edit fields (id is disabled)
  editFields: [
    {
      type: 'text',
      name: 'id',
      get label() { return i18n.t('settings:assistants.field.id'); },
      required: true,
      disabled: true
    },
    {
      type: 'text',
      name: 'name',
      get label() { return i18n.t('settings:assistants.field.name'); },
      get placeholder() { return i18n.t('settings:assistants.field.name.placeholder'); },
      required: true
    },
    {
      type: 'icon-picker' as const,
      name: 'icon',
      get label() { return i18n.t('settings:assistants.field.icon'); },
      get helpText() { return i18n.t('settings:assistants.field.icon.help'); }
    },
    {
      type: 'text',
      name: 'description',
      get label() { return i18n.t('settings:assistants.field.description'); },
      get placeholder() { return i18n.t('settings:assistants.field.description.placeholder'); },
      get helpText() { return i18n.t('settings:assistants.field.description.help'); }
    },
    {
      type: 'select',
      name: 'model_id',
      get label() { return i18n.t('settings:assistants.field.modelId'); },
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
      get helpText() { return i18n.t('settings:assistants.field.modelId.help'); }
    },
    {
      type: 'textarea',
      name: 'system_prompt',
      get label() { return i18n.t('settings:assistants.field.systemPrompt'); },
      get placeholder() { return i18n.t('settings:assistants.field.systemPrompt.placeholder'); },
      rows: 3,
      get helpText() { return i18n.t('settings:assistants.field.systemPrompt.help'); }
    },
    {
      type: 'slider',
      name: 'temperature',
      get label() { return i18n.t('settings:assistants.field.temperature'); },
      min: 0,
      max: 2,
      step: 0.1,
      defaultValue: 0.7,
      showValue: true,
      showLabels: true,
      get minLabel() { return i18n.t('settings:assistants.field.temperature.minLabel'); },
      get maxLabel() { return i18n.t('settings:assistants.field.temperature.maxLabel'); },
      formatValue: (v) => v.toFixed(1),
      get helpText() { return i18n.t('settings:assistants.field.temperature.help'); }
    },
    ...llmParamFields,
    {
      type: 'number',
      name: 'max_rounds',
      get label() { return i18n.t('settings:assistants.field.maxRounds'); },
      get placeholder() { return i18n.t('settings:assistants.field.maxRounds.placeholder'); },
      min: -1,
      get helpText() { return i18n.t('settings:assistants.field.maxRounds.help'); }
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:assistants.field.enabled'); },
      defaultValue: true
    },
    {
      type: 'checkbox',
      name: 'memory_enabled',
      get label() { return i18n.t('settings:assistants.field.memoryEnabled'); },
      defaultValue: false
    },
    {
      type: 'multi-select' as const,
      name: 'knowledge_base_ids',
      get label() { return i18n.t('settings:assistants.field.knowledgeBases'); },
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
      get helpText() { return i18n.t('settings:assistants.field.knowledgeBases.help'); }
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
