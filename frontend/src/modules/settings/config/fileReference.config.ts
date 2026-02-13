/**
 * File Reference Settings Configuration
 *
 * Controls @file preview and injection limits.
 */

import type { SimpleConfigSettingsConfig } from './types';
import i18n from '../../../i18n';

export const fileReferenceConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  get title() { return i18n.t('settings:fileReference.title'); },
  get description() { return i18n.t('settings:fileReference.description'); },

  apiEndpoint: {
    get: '/api/file-reference/config',
    update: '/api/file-reference/config',
  },

  fields: [
    {
      type: 'number',
      name: 'ui_preview_max_chars',
      get label() { return i18n.t('settings:fileReference.field.uiPreviewMaxChars'); },
      min: 100,
      max: 10000,
      defaultValue: 1200,
      required: true,
      get helpText() { return i18n.t('settings:fileReference.field.uiPreviewMaxChars.help'); },
    },
    {
      type: 'number',
      name: 'ui_preview_max_lines',
      get label() { return i18n.t('settings:fileReference.field.uiPreviewMaxLines'); },
      min: 1,
      max: 300,
      defaultValue: 28,
      required: true,
      get helpText() { return i18n.t('settings:fileReference.field.uiPreviewMaxLines.help'); },
    },
    {
      type: 'number',
      name: 'injection_preview_max_chars',
      get label() { return i18n.t('settings:fileReference.field.injectionPreviewMaxChars'); },
      min: 100,
      max: 5000,
      defaultValue: 600,
      required: true,
      get helpText() { return i18n.t('settings:fileReference.field.injectionPreviewMaxChars.help'); },
    },
    {
      type: 'number',
      name: 'injection_preview_max_lines',
      get label() { return i18n.t('settings:fileReference.field.injectionPreviewMaxLines'); },
      min: 1,
      max: 500,
      defaultValue: 40,
      required: true,
      get helpText() { return i18n.t('settings:fileReference.field.injectionPreviewMaxLines.help'); },
    },
    {
      type: 'number',
      name: 'chunk_size',
      get label() { return i18n.t('settings:fileReference.field.chunkSize'); },
      min: 200,
      max: 20000,
      defaultValue: 2500,
      required: true,
      get helpText() { return i18n.t('settings:fileReference.field.chunkSize.help'); },
    },
    {
      type: 'number',
      name: 'max_chunks',
      get label() { return i18n.t('settings:fileReference.field.maxChunks'); },
      min: 1,
      max: 50,
      defaultValue: 6,
      required: true,
      get helpText() { return i18n.t('settings:fileReference.field.maxChunks.help'); },
    },
    {
      type: 'number',
      name: 'total_budget_chars',
      get label() { return i18n.t('settings:fileReference.field.totalBudgetChars'); },
      min: 1000,
      max: 500000,
      defaultValue: 18000,
      required: true,
      get helpText() { return i18n.t('settings:fileReference.field.totalBudgetChars.help'); },
    },
  ],
};

