/**
 * Translation Settings Configuration
 *
 * Defines the structure and behavior of the Translation settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';
import i18n from '../../../i18n';

export const translationConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  get title() { return i18n.t('settings:translationConfig.title'); },
  get description() { return i18n.t('settings:translationConfig.description'); },

  apiEndpoint: {
    get: '/api/translation/config',
    update: '/api/translation/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:translationConfig.field.enabled'); },
      get helpText() { return i18n.t('settings:translationConfig.field.enabled.help'); }
    },
    {
      type: 'text',
      name: 'target_language',
      get label() { return i18n.t('settings:translationConfig.field.targetLanguage'); },
      required: true,
      get helpText() { return i18n.t('settings:translationConfig.field.targetLanguage.help'); }
    },
    {
      type: 'text',
      name: 'input_target_language',
      get label() { return i18n.t('settings:translationConfig.field.inputTargetLanguage'); },
      required: true,
      get helpText() { return i18n.t('settings:translationConfig.field.inputTargetLanguage.help'); }
    },
    {
      type: 'select',
      name: 'model_id',
      get label() { return i18n.t('settings:translationConfig.field.modelId'); },
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models.map((m: any) => ({
          value: `${m.provider_id}:${m.id}`,
          label: m.name || m.id
        }));
      },
      get helpText() { return i18n.t('settings:translationConfig.field.modelId.help'); }
    },
    {
      type: 'slider',
      name: 'temperature',
      get label() { return i18n.t('settings:translationConfig.field.temperature'); },
      min: 0,
      max: 2,
      step: 0.1,
      defaultValue: 0.3,
      get helpText() { return i18n.t('settings:translationConfig.field.temperature.help'); }
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      get label() { return i18n.t('settings:translationConfig.field.timeout'); },
      min: 10,
      max: 300,
      defaultValue: 30,
      required: true,
      get helpText() { return i18n.t('settings:translationConfig.field.timeout.help'); }
    },
    {
      type: 'textarea',
      name: 'prompt_template',
      get label() { return i18n.t('settings:translationConfig.field.promptTemplate'); },
      rows: 10,
      monospace: true,
      get placeholder() { return i18n.t('settings:translationConfig.field.promptTemplate.placeholder'); },
      get helpText() { return i18n.t('settings:translationConfig.field.promptTemplate.help'); }
    }
  ]
};
