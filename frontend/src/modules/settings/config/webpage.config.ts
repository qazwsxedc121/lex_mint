/**
 * Webpage Settings Configuration
 *
 * Defines the structure and behavior of the Webpage settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';
import i18n from '../../../i18n';

export const webpageConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  get title() { return i18n.t('settings:webpage.title'); },
  get description() { return i18n.t('settings:webpage.description'); },

  apiEndpoint: {
    get: '/api/webpage/config',
    update: '/api/webpage/config'
  },

  fields: [
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:webpage.field.enabled'); },
      defaultValue: true
    },
    {
      type: 'number',
      name: 'max_urls',
      get label() { return i18n.t('settings:webpage.field.maxUrls'); },
      min: 1,
      max: 10,
      defaultValue: 2,
      required: true,
      get helpText() { return i18n.t('settings:webpage.field.maxUrls.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      get label() { return i18n.t('settings:webpage.field.timeout'); },
      min: 5,
      max: 60,
      defaultValue: 10,
      required: true,
      get helpText() { return i18n.t('settings:webpage.field.timeout.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'max_bytes',
      get label() { return i18n.t('settings:webpage.field.maxBytes'); },
      min: 100000,
      max: 10000000,
      step: 100000,
      defaultValue: 3000000,
      required: true,
      get helpText() { return i18n.t('settings:webpage.field.maxBytes.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'max_content_chars',
      get label() { return i18n.t('settings:webpage.field.maxContentChars'); },
      min: 1000,
      max: 100000,
      step: 1000,
      defaultValue: 20000,
      required: true,
      get helpText() { return i18n.t('settings:webpage.field.maxContentChars.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'text',
      name: 'user_agent',
      get label() { return i18n.t('settings:webpage.field.userAgent'); },
      get placeholder() { return i18n.t('settings:webpage.field.userAgent.placeholder'); },
      get helpText() { return i18n.t('settings:webpage.field.userAgent.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'text',
      name: 'proxy',
      get label() { return i18n.t('settings:webpage.field.proxy'); },
      get placeholder() { return i18n.t('settings:webpage.field.proxy.placeholder'); },
      get helpText() { return i18n.t('settings:webpage.field.proxy.help'); },
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'checkbox',
      name: 'trust_env',
      get label() { return i18n.t('settings:webpage.field.trustEnv'); },
      defaultValue: true,
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'checkbox',
      name: 'diagnostics_enabled',
      get label() { return i18n.t('settings:webpage.field.diagnosticsEnabled'); },
      defaultValue: true,
      condition: (formData) => formData.enabled !== false
    },
    {
      type: 'number',
      name: 'diagnostics_timeout_seconds',
      get label() { return i18n.t('settings:webpage.field.diagnosticsTimeout'); },
      min: 1,
      max: 10,
      defaultValue: 2,
      required: true,
      get helpText() { return i18n.t('settings:webpage.field.diagnosticsTimeout.help'); },
      condition: (formData) => formData.enabled !== false && formData.diagnostics_enabled !== false
    }
  ]
};
