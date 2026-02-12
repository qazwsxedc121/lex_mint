/**
 * TTS Settings Configuration
 *
 * Defines the structure and behavior of the Text-to-Speech settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';
import i18n from '../../../i18n';

export const ttsConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  get title() { return i18n.t('settings:tts.title'); },
  get description() { return i18n.t('settings:tts.description'); },

  apiEndpoint: {
    get: '/api/tts/config',
    update: '/api/tts/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:tts.field.enabled'); },
      get helpText() { return i18n.t('settings:tts.field.enabled.help'); }
    },
    {
      type: 'text',
      name: 'voice',
      get label() { return i18n.t('settings:tts.field.voice'); },
      required: true,
      get helpText() { return i18n.t('settings:tts.field.voice.help'); }
    },
    {
      type: 'text',
      name: 'voice_zh',
      get label() { return i18n.t('settings:tts.field.voiceZh'); },
      required: true,
      get helpText() { return i18n.t('settings:tts.field.voiceZh.help'); }
    },
    {
      type: 'text',
      name: 'rate',
      get label() { return i18n.t('settings:tts.field.rate'); },
      required: true,
      get helpText() { return i18n.t('settings:tts.field.rate.help'); }
    },
    {
      type: 'text',
      name: 'volume',
      get label() { return i18n.t('settings:tts.field.volume'); },
      required: true,
      get helpText() { return i18n.t('settings:tts.field.volume.help'); }
    },
    {
      type: 'number',
      name: 'max_text_length',
      get label() { return i18n.t('settings:tts.field.maxTextLength'); },
      min: 100,
      max: 100000,
      defaultValue: 10000,
      required: true,
      get helpText() { return i18n.t('settings:tts.field.maxTextLength.help'); }
    }
  ]
};
