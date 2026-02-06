/**
 * Follow-up Questions Settings Configuration
 *
 * Defines the structure and behavior of the Follow-up Questions settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';

export const followupConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  title: 'Follow-up Questions Settings',
  description: 'Configure automatic follow-up question suggestions after each chat response',

  apiEndpoint: {
    get: '/api/followup/config',
    update: '/api/followup/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable follow-up question suggestions',
      defaultValue: true
    },
    {
      type: 'number',
      name: 'count',
      label: 'Number of Suggestions',
      min: 0,
      max: 5,
      defaultValue: 3,
      required: true,
      helpText: 'How many follow-up questions to generate (0 to disable)',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'select',
      name: 'model_id',
      label: 'Model for Follow-up Generation',
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models.map((m: any) => ({
          value: `${m.provider_id}:${m.id}`,
          label: m.name || m.id
        }));
      },
      helpText: 'Recommended: Use a small, fast model to minimize latency',
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
      defaultValue: 15,
      required: true,
      helpText: 'Maximum time to wait for follow-up generation',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'textarea',
      name: 'prompt_template',
      label: 'Prompt Template',
      rows: 8,
      monospace: true,
      placeholder: 'Enter prompt template. Use {count} and {conversation_text} as placeholders.',
      helpText: 'Use {count} for number of questions and {conversation_text} for conversation content',
      condition: (formData) => formData.enabled !== false
    }
  ]
};
