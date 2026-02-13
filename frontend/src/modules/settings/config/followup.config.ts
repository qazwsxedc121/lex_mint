/**
 * Follow-up Questions Settings Configuration
 *
 * Defines the structure and behavior of the Follow-up Questions settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';
import i18n from '../../../i18n';

export const followupConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  get title() { return i18n.t('settings:followup.title'); },
  get description() { return i18n.t('settings:followup.description'); },

  apiEndpoint: {
    get: '/api/followup/config',
    update: '/api/followup/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:followup.field.enabled'); },
      defaultValue: true
    },
    {
      type: 'number',
      name: 'count',
      get label() { return i18n.t('settings:followup.field.count'); },
      min: 0,
      max: 5,
      defaultValue: 3,
      required: true,
      get helpText() { return i18n.t('settings:followup.field.count.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'select',
      name: 'model_id',
      get label() { return i18n.t('settings:followup.field.modelId'); },
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models.map((m: any) => ({
          value: `${m.provider_id}:${m.id}`,
          label: m.name || m.id
        }));
      },
      get helpText() { return i18n.t('settings:followup.field.modelId.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'max_context_rounds',
      get label() { return i18n.t('settings:followup.field.maxContextRounds'); },
      min: 1,
      max: 10,
      defaultValue: 3,
      required: true,
      get helpText() { return i18n.t('settings:followup.field.maxContextRounds.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      get label() { return i18n.t('settings:followup.field.timeout'); },
      min: 5,
      max: 60,
      defaultValue: 15,
      required: true,
      get helpText() { return i18n.t('settings:followup.field.timeout.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'textarea',
      name: 'prompt_template',
      get label() { return i18n.t('settings:followup.field.promptTemplate'); },
      rows: 8,
      monospace: true,
      get placeholder() { return i18n.t('settings:followup.field.promptTemplate.placeholder'); },
      get helpText() { return i18n.t('settings:followup.field.promptTemplate.help'); },
      condition: (formData) => formData.enabled !== false
    }
  ]
};
