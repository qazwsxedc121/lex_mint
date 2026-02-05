/**
 * Search Settings Configuration
 *
 * Defines the structure and behavior of the Search settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';

export const searchConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  title: 'Search Settings',
  description: 'Choose a search provider for the chat web search toggle',

  apiEndpoint: {
    get: '/api/search/config',
    update: '/api/search/config'
  },

  fields: [
    {
      type: 'select',
      name: 'provider',
      label: 'Search Provider',
      required: true,
      defaultValue: 'duckduckgo',
      options: [
        {
          value: 'duckduckgo',
          label: 'DuckDuckGo (Free, no API key required)'
        },
        {
          value: 'tavily',
          label: 'Tavily (Higher quality, requires API key)'
        }
      ],
      helpText: 'Select the search provider for web searches'
    },
    {
      type: 'number',
      name: 'max_results',
      label: 'Max Results',
      min: 1,
      max: 20,
      defaultValue: 6,
      required: true,
      helpText: 'Maximum number of search results to return'
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      label: 'Timeout (seconds)',
      min: 5,
      max: 60,
      defaultValue: 10,
      required: true,
      helpText: 'Maximum time to wait for search results'
    }
  ]
};
