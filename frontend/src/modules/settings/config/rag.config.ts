/**
 * RAG Settings Configuration
 *
 * Defines the structure and behavior of the RAG settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';
import i18n from '../../../i18n';

export const ragConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  get title() { return i18n.t('settings:rag.title'); },
  get description() { return i18n.t('settings:rag.description'); },

  apiEndpoint: {
    get: '/api/rag/config',
    update: '/api/rag/config'
  },

  fields: [
    {
      type: 'select',
      name: 'embedding_provider',
      get label() { return i18n.t('settings:rag.field.embeddingProvider'); },
      required: true,
      defaultValue: 'api',
      get options() {
        return [
          { value: 'api', label: i18n.t('settings:rag.opt.api') },
          { value: 'local', label: i18n.t('settings:rag.opt.local') }
        ];
      },
      get helpText() { return i18n.t('settings:rag.field.embeddingProvider.help'); }
    },
    {
      type: 'text',
      name: 'embedding_api_model',
      get label() { return i18n.t('settings:rag.field.embeddingApiModel'); },
      get placeholder() { return i18n.t('settings:rag.field.embeddingApiModel.placeholder'); },
      defaultValue: 'jina-embeddings-v3',
      get helpText() { return i18n.t('settings:rag.field.embeddingApiModel.help'); },
      condition: (formData) => formData.embedding_provider === 'api',
    },
    {
      type: 'text',
      name: 'embedding_api_base_url',
      get label() { return i18n.t('settings:rag.field.embeddingApiBaseUrl'); },
      get placeholder() { return i18n.t('settings:rag.field.embeddingApiBaseUrl.placeholder'); },
      defaultValue: '',
      get helpText() { return i18n.t('settings:rag.field.embeddingApiBaseUrl.help'); },
      condition: (formData) => formData.embedding_provider === 'api',
    },
    {
      type: 'password',
      name: 'embedding_api_key',
      get label() { return i18n.t('settings:rag.field.embeddingApiKey'); },
      get placeholder() { return i18n.t('settings:rag.field.embeddingApiKey.placeholder'); },
      defaultValue: '',
      get helpText() { return i18n.t('settings:rag.field.embeddingApiKey.help'); },
      condition: (formData) => formData.embedding_provider === 'api',
    },
    {
      type: 'text',
      name: 'embedding_local_model',
      get label() { return i18n.t('settings:rag.field.embeddingLocalModel'); },
      get placeholder() { return i18n.t('settings:rag.field.embeddingLocalModel.placeholder'); },
      defaultValue: 'all-MiniLM-L6-v2',
      get helpText() { return i18n.t('settings:rag.field.embeddingLocalModel.help'); },
      condition: (formData) => formData.embedding_provider === 'local',
    },
    {
      type: 'select',
      name: 'embedding_local_device',
      get label() { return i18n.t('settings:rag.field.embeddingLocalDevice'); },
      defaultValue: 'cpu',
      options: [
        { value: 'cpu', label: 'CPU' },
        { value: 'cuda', label: 'CUDA (GPU)' }
      ],
      get helpText() { return i18n.t('settings:rag.field.embeddingLocalDevice.help'); },
      condition: (formData) => formData.embedding_provider === 'local',
    },
    {
      type: 'number',
      name: 'chunk_size',
      get label() { return i18n.t('settings:rag.field.chunkSize'); },
      min: 100,
      max: 10000,
      defaultValue: 1000,
      required: true,
      get helpText() { return i18n.t('settings:rag.field.chunkSize.help'); }
    },
    {
      type: 'number',
      name: 'chunk_overlap',
      get label() { return i18n.t('settings:rag.field.chunkOverlap'); },
      min: 0,
      max: 5000,
      defaultValue: 200,
      required: true,
      get helpText() { return i18n.t('settings:rag.field.chunkOverlap.help'); }
    },
    {
      type: 'number',
      name: 'top_k',
      get label() { return i18n.t('settings:rag.field.topK'); },
      min: 1,
      max: 50,
      defaultValue: 5,
      required: true,
      get helpText() { return i18n.t('settings:rag.field.topK.help'); }
    },
    {
      type: 'number',
      name: 'score_threshold',
      get label() { return i18n.t('settings:rag.field.scoreThreshold'); },
      min: 0,
      max: 1,
      step: 0.05,
      defaultValue: 0.3,
      required: true,
      get helpText() { return i18n.t('settings:rag.field.scoreThreshold.help'); }
    }
  ]
};
