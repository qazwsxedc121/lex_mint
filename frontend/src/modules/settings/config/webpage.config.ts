/**
 * Webpage Settings Configuration
 *
 * Defines the structure and behavior of the Webpage settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';

export const webpageConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  title: 'Webpage Settings',
  description: 'Configure webpage fetch and proxy settings',

  apiEndpoint: {
    get: '/api/webpage/config',
    update: '/api/webpage/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable webpage fetching',
      defaultValue: true
    },
    {
      type: 'number',
      name: 'max_urls',
      label: 'Max URLs per request',
      min: 1,
      max: 10,
      defaultValue: 2,
      required: true,
      helpText: 'Maximum number of URLs to fetch in a single request',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      label: 'Timeout (seconds)',
      min: 5,
      max: 60,
      defaultValue: 10,
      required: true,
      helpText: 'Maximum time to wait for webpage fetch',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'max_bytes',
      label: 'Max Download Size (bytes)',
      min: 100000,
      max: 10000000,
      step: 100000,
      defaultValue: 3000000,
      required: true,
      helpText: 'Maximum size of webpage to download',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'max_content_chars',
      label: 'Max Content Characters',
      min: 1000,
      max: 100000,
      step: 1000,
      defaultValue: 20000,
      required: true,
      helpText: 'Maximum length of extracted text content',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'text',
      name: 'user_agent',
      label: 'User Agent',
      placeholder: 'agent_dev/1.0',
      helpText: 'Custom User-Agent header for requests',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'text',
      name: 'proxy',
      label: 'Proxy URL',
      placeholder: 'http://proxy.example.com:8080',
      helpText: 'HTTP/HTTPS proxy URL (leave empty to disable)',
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'checkbox',
      name: 'trust_env',
      label: 'Trust environment proxy settings',
      defaultValue: true,
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'checkbox',
      name: 'diagnostics_enabled',
      label: 'Enable network diagnostics',
      defaultValue: true,
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'diagnostics_timeout_seconds',
      label: 'Diagnostics Timeout (seconds)',
      min: 1,
      max: 10,
      defaultValue: 2,
      required: true,
      helpText: 'Timeout for network diagnostics checks',
      condition: (formData) => formData.enabled !== false && formData.diagnostics_enabled !== false
    }
  ]
};
