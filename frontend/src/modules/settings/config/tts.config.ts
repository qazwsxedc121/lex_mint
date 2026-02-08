/**
 * TTS Settings Configuration
 *
 * Defines the structure and behavior of the Text-to-Speech settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';

export const ttsConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  title: 'Text-to-Speech Settings',
  description: 'Configure text-to-speech synthesis using Edge TTS (Microsoft neural voices)',

  apiEndpoint: {
    get: '/api/tts/config',
    update: '/api/tts/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable TTS',
      helpText: 'Enable or disable the text-to-speech feature'
    },
    {
      type: 'text',
      name: 'voice',
      label: 'Default Voice',
      required: true,
      helpText: 'Edge TTS voice for English and other languages (e.g., en-US-AriaNeural, en-US-GuyNeural)'
    },
    {
      type: 'text',
      name: 'voice_zh',
      label: 'Chinese Voice',
      required: true,
      helpText: 'Edge TTS voice for Chinese text (e.g., zh-CN-XiaoxiaoNeural, zh-CN-YunxiNeural). Auto-selected when Chinese text is detected.'
    },
    {
      type: 'text',
      name: 'rate',
      label: 'Speech Rate',
      required: true,
      helpText: 'Speech rate adjustment (e.g., +0%, +20%, -10%)'
    },
    {
      type: 'text',
      name: 'volume',
      label: 'Volume',
      required: true,
      helpText: 'Volume adjustment (e.g., +0%, +50%, -20%)'
    },
    {
      type: 'number',
      name: 'max_text_length',
      label: 'Max Text Length',
      min: 100,
      max: 100000,
      defaultValue: 10000,
      required: true,
      helpText: 'Maximum number of characters to synthesize. Longer text will be truncated.'
    }
  ]
};
