/**
 * Title Generation Settings Configuration
 *
 * Defines the structure and behavior of the Title Generation settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';
import i18n from '../../../i18n';

export const titleGenerationConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  get title() { return i18n.t('settings:titleGen.title'); },
  get description() { return i18n.t('settings:titleGen.description'); },

  apiEndpoint: {
    get: '/api/title-generation/config',
    update: '/api/title-generation/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:titleGen.field.enabled'); },
      defaultValue: true
    },
    {
      type: 'number',
      name: 'trigger_threshold',
      get label() { return i18n.t('settings:titleGen.field.triggerThreshold'); },
      min: 1,
      max: 10,
      defaultValue: 1,
      required: true,
      get helpText() { return i18n.t('settings:titleGen.field.triggerThreshold.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'select',
      name: 'model_id',
      get label() { return i18n.t('settings:titleGen.field.modelId'); },
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models.map((m: any) => ({
          value: `${m.provider_id}:${m.id}`,
          label: m.name || m.id
        }));
      },
      get helpText() { return i18n.t('settings:titleGen.field.modelId.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'max_context_rounds',
      get label() { return i18n.t('settings:titleGen.field.maxContextRounds'); },
      min: 1,
      max: 10,
      defaultValue: 3,
      required: true,
      get helpText() { return i18n.t('settings:titleGen.field.maxContextRounds.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      get label() { return i18n.t('settings:titleGen.field.timeout'); },
      min: 5,
      max: 60,
      defaultValue: 10,
      required: true,
      get helpText() { return i18n.t('settings:titleGen.field.timeout.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'textarea',
      name: 'prompt_template',
      get label() { return i18n.t('settings:titleGen.field.promptTemplate'); },
      rows: 6,
      monospace: true,
      get placeholder() { return i18n.t('settings:titleGen.field.promptTemplate.placeholder'); },
      get helpText() { return i18n.t('settings:titleGen.field.promptTemplate.help'); },
      condition: (formData) => formData.enabled !== false
    }
  ]
};
