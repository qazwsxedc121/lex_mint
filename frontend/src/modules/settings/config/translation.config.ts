/**
 * Translation Settings Configuration
 *
 * Defines the structure and behavior of the Translation settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';

export const translationConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  title: 'Translation Settings',
  description: 'Configure Q&A translation for translating LLM responses and user input',

  apiEndpoint: {
    get: '/api/translation/config',
    update: '/api/translation/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable Translation',
      helpText: 'Enable or disable the translation feature'
    },
    {
      type: 'text',
      name: 'target_language',
      label: 'Response Translation Language',
      required: true,
      helpText: 'Language to translate LLM responses into (e.g., Chinese, Japanese, Korean)'
    },
    {
      type: 'text',
      name: 'input_target_language',
      label: 'Input Translation Language',
      required: true,
      helpText: 'Language to translate user input into before sending to LLM (e.g., English)'
    },
    {
      type: 'select',
      name: 'model_id',
      label: 'Translation Model',
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models.map((m: any) => ({
          value: `${m.provider_id}:${m.id}`,
          label: m.name || m.id
        }));
      },
      helpText: 'Model used for translation. A fast model is recommended.'
    },
    {
      type: 'slider',
      name: 'temperature',
      label: 'Temperature',
      min: 0,
      max: 2,
      step: 0.1,
      defaultValue: 0.3,
      helpText: 'Lower values produce more accurate translations. Recommended: 0.1 - 0.5'
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      label: 'Timeout (seconds)',
      min: 10,
      max: 300,
      defaultValue: 30,
      required: true,
      helpText: 'Maximum time to wait for the translation LLM call'
    },
    {
      type: 'textarea',
      name: 'prompt_template',
      label: 'Translation Prompt',
      rows: 10,
      monospace: true,
      placeholder: 'Enter translation prompt. Use {text} and {target_language} as placeholders.',
      helpText: 'Use {text} for the content to translate and {target_language} for the target language'
    }
  ]
};
