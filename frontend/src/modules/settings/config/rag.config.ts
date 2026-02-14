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
          { value: 'local', label: i18n.t('settings:rag.opt.local') },
          { value: 'local_gguf', label: i18n.t('settings:rag.opt.localGguf') }
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
      type: 'text',
      name: 'embedding_local_gguf_model_path',
      get label() { return i18n.t('settings:rag.field.embeddingLocalGgufModelPath'); },
      get placeholder() { return i18n.t('settings:rag.field.embeddingLocalGgufModelPath.placeholder'); },
      defaultValue: 'models/embeddings/qwen3-embedding-0.6b.gguf',
      get helpText() { return i18n.t('settings:rag.field.embeddingLocalGgufModelPath.help'); },
      condition: (formData) => formData.embedding_provider === 'local_gguf',
    },
    {
      type: 'number',
      name: 'embedding_local_gguf_n_ctx',
      get label() { return i18n.t('settings:rag.field.embeddingLocalGgufCtx'); },
      min: 256,
      max: 65536,
      defaultValue: 2048,
      get helpText() { return i18n.t('settings:rag.field.embeddingLocalGgufCtx.help'); },
      condition: (formData) => formData.embedding_provider === 'local_gguf',
    },
    {
      type: 'number',
      name: 'embedding_local_gguf_n_threads',
      get label() { return i18n.t('settings:rag.field.embeddingLocalGgufThreads'); },
      min: 0,
      max: 256,
      defaultValue: 0,
      get helpText() { return i18n.t('settings:rag.field.embeddingLocalGgufThreads.help'); },
      condition: (formData) => formData.embedding_provider === 'local_gguf',
    },
    {
      type: 'number',
      name: 'embedding_local_gguf_n_gpu_layers',
      get label() { return i18n.t('settings:rag.field.embeddingLocalGgufGpuLayers'); },
      min: 0,
      max: 1024,
      defaultValue: 0,
      get helpText() { return i18n.t('settings:rag.field.embeddingLocalGgufGpuLayers.help'); },
      condition: (formData) => formData.embedding_provider === 'local_gguf',
    },
    {
      type: 'checkbox',
      name: 'embedding_local_gguf_normalize',
      get label() { return i18n.t('settings:rag.field.embeddingLocalGgufNormalize'); },
      defaultValue: true,
      get helpText() { return i18n.t('settings:rag.field.embeddingLocalGgufNormalize.help'); },
      condition: (formData) => formData.embedding_provider === 'local_gguf',
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
      name: 'recall_k',
      get label() { return i18n.t('settings:rag.field.recallK'); },
      min: 1,
      max: 200,
      defaultValue: 20,
      required: true,
      get helpText() { return i18n.t('settings:rag.field.recallK.help'); }
    },
    {
      type: 'number',
      name: 'max_per_doc',
      get label() { return i18n.t('settings:rag.field.maxPerDoc'); },
      min: 1,
      max: 20,
      defaultValue: 2,
      required: true,
      get helpText() { return i18n.t('settings:rag.field.maxPerDoc.help'); }
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
    },
    {
      type: 'select',
      name: 'reorder_strategy',
      get label() { return i18n.t('settings:rag.field.reorderStrategy'); },
      defaultValue: 'long_context',
      options: [
        { value: 'long_context', label: i18n.t('settings:rag.opt.longContext') },
        { value: 'none', label: i18n.t('settings:rag.opt.none') }
      ],
      required: true,
      get helpText() { return i18n.t('settings:rag.field.reorderStrategy.help'); }
    },
    {
      type: 'checkbox',
      name: 'rerank_enabled',
      get label() { return i18n.t('settings:rag.field.rerankEnabled'); },
      defaultValue: false,
      get helpText() { return i18n.t('settings:rag.field.rerankEnabled.help'); }
    },
    {
      type: 'text',
      name: 'rerank_api_model',
      get label() { return i18n.t('settings:rag.field.rerankApiModel'); },
      get placeholder() { return i18n.t('settings:rag.field.rerankApiModel.placeholder'); },
      defaultValue: 'jina-reranker-v2-base-multilingual',
      get helpText() { return i18n.t('settings:rag.field.rerankApiModel.help'); },
      condition: (formData) => formData.rerank_enabled === true,
    },
    {
      type: 'text',
      name: 'rerank_api_base_url',
      get label() { return i18n.t('settings:rag.field.rerankApiBaseUrl'); },
      get placeholder() { return i18n.t('settings:rag.field.rerankApiBaseUrl.placeholder'); },
      defaultValue: 'https://api.jina.ai/v1/rerank',
      get helpText() { return i18n.t('settings:rag.field.rerankApiBaseUrl.help'); },
      condition: (formData) => formData.rerank_enabled === true,
    },
    {
      type: 'password',
      name: 'rerank_api_key',
      get label() { return i18n.t('settings:rag.field.rerankApiKey'); },
      get placeholder() { return i18n.t('settings:rag.field.rerankApiKey.placeholder'); },
      defaultValue: '',
      get helpText() { return i18n.t('settings:rag.field.rerankApiKey.help'); },
      condition: (formData) => formData.rerank_enabled === true,
    },
    {
      type: 'number',
      name: 'rerank_timeout_seconds',
      get label() { return i18n.t('settings:rag.field.rerankTimeoutSeconds'); },
      min: 1,
      max: 120,
      defaultValue: 20,
      required: true,
      get helpText() { return i18n.t('settings:rag.field.rerankTimeoutSeconds.help'); },
      condition: (formData) => formData.rerank_enabled === true,
    },
    {
      type: 'number',
      name: 'rerank_weight',
      get label() { return i18n.t('settings:rag.field.rerankWeight'); },
      min: 0,
      max: 1,
      step: 0.05,
      defaultValue: 0.7,
      required: true,
      get helpText() { return i18n.t('settings:rag.field.rerankWeight.help'); },
      condition: (formData) => formData.rerank_enabled === true,
    }
  ]
};
