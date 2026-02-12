/**
 * Search Settings Configuration
 *
 * Defines the structure and behavior of the Search settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';
import i18n from '../../../i18n';

export const searchConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  get title() { return i18n.t('settings:search.title'); },
  get description() { return i18n.t('settings:search.description'); },

  apiEndpoint: {
    get: '/api/search/config',
    update: '/api/search/config'
  },

  fields: [
    {
      type: 'select',
      name: 'provider',
      get label() { return i18n.t('settings:search.field.provider'); },
      required: true,
      defaultValue: 'duckduckgo',
      get options() {
        return [
          { value: 'duckduckgo', label: i18n.t('settings:search.opt.duckduckgo') },
          { value: 'tavily', label: i18n.t('settings:search.opt.tavily') }
        ];
      },
      get helpText() { return i18n.t('settings:search.field.provider.help'); }
    },
    {
      type: 'number',
      name: 'max_results',
      get label() { return i18n.t('settings:search.field.maxResults'); },
      min: 1,
      max: 20,
      defaultValue: 6,
      required: true,
      get helpText() { return i18n.t('settings:search.field.maxResults.help'); }
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      get label() { return i18n.t('settings:search.field.timeout'); },
      min: 5,
      max: 60,
      defaultValue: 10,
      required: true,
      get helpText() { return i18n.t('settings:search.field.timeout.help'); }
    }
  ]
};
