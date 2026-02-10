/**
 * Compression Settings Configuration
 *
 * Defines the structure and behavior of the Context Compression settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';

export const compressionConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  title: 'Context Compression Settings',
  description: 'Configure how conversation context is compressed (summarized) to free up the context window',

  apiEndpoint: {
    get: '/api/compression/config',
    update: '/api/compression/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'auto_compress_enabled',
      label: 'Enable Auto-Compression',
      defaultValue: false
    },
    {
      type: 'slider',
      name: 'auto_compress_threshold',
      label: 'Auto-Compression Threshold',
      min: 0.1,
      max: 0.9,
      step: 0.05,
      defaultValue: 0.5,
      helpText: 'Compression triggers when token usage exceeds this ratio of the context window (e.g. 0.5 = 50%)',
      condition: (formData) => formData.auto_compress_enabled === true
    },
    {
      type: 'select',
      name: 'model_id',
      label: 'Compression Model',
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models.map((m: any) => ({
          value: `${m.provider_id}:${m.id}`,
          label: m.name || m.id
        }));
      },
      helpText: 'Model used to generate the conversation summary. A fast model is recommended.'
    },
    {
      type: 'slider',
      name: 'temperature',
      label: 'Temperature',
      min: 0,
      max: 2,
      step: 0.1,
      defaultValue: 0.3,
      helpText: 'Lower values produce more factual summaries. Recommended: 0.2 - 0.5'
    },
    {
      type: 'number',
      name: 'min_messages',
      label: 'Minimum Messages to Compress',
      min: 1,
      max: 50,
      defaultValue: 2,
      required: true,
      helpText: 'Minimum number of messages required before compression is allowed'
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      label: 'Timeout (seconds)',
      min: 10,
      max: 300,
      defaultValue: 60,
      required: true,
      helpText: 'Maximum time to wait for the compression LLM call'
    },
    {
      type: 'textarea',
      name: 'prompt_template',
      label: 'Summarization Prompt',
      rows: 10,
      monospace: true,
      placeholder: 'Enter summarization prompt. Use {formatted_messages} as placeholder for conversation content.',
      helpText: 'Use {formatted_messages} where the conversation text should be inserted'
    }
  ]
};
