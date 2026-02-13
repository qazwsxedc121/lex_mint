/**
 * Compression Settings Configuration
 *
 * Defines the structure and behavior of the Context Compression settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';
import i18n from '../../../i18n';

export const compressionConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  get title() { return i18n.t('settings:compression.title'); },
  get description() { return i18n.t('settings:compression.description'); },

  apiEndpoint: {
    get: '/api/compression/config',
    update: '/api/compression/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'auto_compress_enabled',
      get label() { return i18n.t('settings:compression.field.autoCompress'); },
      defaultValue: false
    },
    {
      type: 'slider',
      name: 'auto_compress_threshold',
      get label() { return i18n.t('settings:compression.field.threshold'); },
      min: 0.1,
      max: 0.9,
      step: 0.05,
      defaultValue: 0.5,
      get helpText() { return i18n.t('settings:compression.field.threshold.help'); },
      condition: (formData) => formData.auto_compress_enabled === true
    },
    {
      type: 'select',
      name: 'model_id',
      get label() { return i18n.t('settings:compression.field.modelId'); },
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models.map((m: any) => ({
          value: `${m.provider_id}:${m.id}`,
          label: m.name || m.id
        }));
      },
      get helpText() { return i18n.t('settings:compression.field.modelId.help'); }
    },
    {
      type: 'slider',
      name: 'temperature',
      get label() { return i18n.t('settings:compression.field.temperature'); },
      min: 0,
      max: 2,
      step: 0.1,
      defaultValue: 0.3,
      get helpText() { return i18n.t('settings:compression.field.temperature.help'); }
    },
    {
      type: 'number',
      name: 'min_messages',
      get label() { return i18n.t('settings:compression.field.minMessages'); },
      min: 1,
      max: 50,
      defaultValue: 2,
      required: true,
      get helpText() { return i18n.t('settings:compression.field.minMessages.help'); }
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      get label() { return i18n.t('settings:compression.field.timeout'); },
      min: 10,
      max: 300,
      defaultValue: 60,
      required: true,
      get helpText() { return i18n.t('settings:compression.field.timeout.help'); }
    },
    {
      type: 'textarea',
      name: 'prompt_template',
      get label() { return i18n.t('settings:compression.field.promptTemplate'); },
      rows: 10,
      monospace: true,
      get placeholder() { return i18n.t('settings:compression.field.promptTemplate.placeholder'); },
      get helpText() { return i18n.t('settings:compression.field.promptTemplate.help'); }
    }
  ]
};
