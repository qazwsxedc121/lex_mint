/**
 * Title Generation Settings Configuration
 *
 * Defines the structure and behavior of the Title Generation settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';

export const titleGenerationConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  title: 'Title Generation Settings',
  description: 'Configure automatic conversation title generation using a small language model',

  apiEndpoint: {
    get: '/api/title-generation/config',
    update: '/api/title-generation/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable automatic title generation',
      defaultValue: true
    },
    {
      type: 'number',
      name: 'trigger_threshold',
      label: 'Trigger Threshold (conversation rounds)',
      min: 1,
      max: 10,
      defaultValue: 1,
      required: true,
      helpText: 'Generate title after this many conversation rounds (1 round = user message + assistant response)',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'select',
      name: 'model_id',
      label: 'Small Model for Title Generation',
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models.map((m: any) => ({
          value: `${m.provider_id}:${m.id}`,
          label: m.name || m.id
        }));
      },
      helpText: 'Recommended: Use a small, fast model like GPT-4o-mini to minimize cost',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'max_context_rounds',
      label: 'Max Context Rounds',
      min: 1,
      max: 10,
      defaultValue: 3,
      required: true,
      helpText: 'Maximum number of recent conversation rounds to use as context',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      label: 'Timeout (seconds)',
      min: 5,
      max: 60,
      defaultValue: 10,
      required: true,
      helpText: 'Maximum time to wait for title generation',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'textarea',
      name: 'prompt_template',
      label: 'Prompt Template',
      rows: 6,
      monospace: true,
      placeholder: 'Enter prompt template. Use {conversation_text} as placeholder for conversation content.',
      helpText: 'Use {conversation_text} as a placeholder for the actual conversation content',
      condition: (formData) => formData.enabled !== false
    }
  ]
};
