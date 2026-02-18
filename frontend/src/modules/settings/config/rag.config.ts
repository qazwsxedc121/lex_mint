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
      type: 'preset',
      name: 'retrieval_preset',
      get label() { return i18n.t('settings:rag.field.retrievalPreset'); },
      get helpText() { return i18n.t('settings:rag.field.retrievalPreset.help'); },
      options: [
        {
          value: 'fast',
          get label() { return i18n.t('settings:rag.opt.presetFast'); },
          get description() { return i18n.t('settings:rag.opt.presetFast.desc'); },
          effects: { top_k: 3, recall_k: 10, max_per_doc: 1, score_threshold: 0.4 }
        },
        {
          value: 'balanced',
          get label() { return i18n.t('settings:rag.opt.presetBalanced'); },
          get description() { return i18n.t('settings:rag.opt.presetBalanced.desc'); },
          effects: { top_k: 5, recall_k: 20, max_per_doc: 2, score_threshold: 0.3 }
        },
        {
          value: 'deep',
          get label() { return i18n.t('settings:rag.opt.presetDeep'); },
          get description() { return i18n.t('settings:rag.opt.presetDeep.desc'); },
          effects: { top_k: 10, recall_k: 50, max_per_doc: 3, score_threshold: 0.2 }
        }
      ]
    },
    {
      type: 'select',
      name: 'vector_store_backend',
      get label() { return i18n.t('settings:rag.field.vectorStoreBackend'); },
      defaultValue: 'sqlite_vec',
      options: [
        { value: 'sqlite_vec', label: i18n.t('settings:rag.opt.vectorStoreSqliteVec') },
        { value: 'chroma', label: i18n.t('settings:rag.opt.vectorStoreChroma') }
      ],
      required: true,
      get helpText() { return i18n.t('settings:rag.field.vectorStoreBackend.help'); }
    },
    {
      type: 'text',
      name: 'vector_sqlite_path',
      get label() { return i18n.t('settings:rag.field.vectorSqlitePath'); },
      get placeholder() { return i18n.t('settings:rag.field.vectorSqlitePath.placeholder'); },
      defaultValue: 'data/state/rag_vec.sqlite3',
      get helpText() { return i18n.t('settings:rag.field.vectorSqlitePath.help'); },
      condition: (formData) => formData.vector_store_backend === 'sqlite_vec',
    },
    {
      type: 'text',
      name: 'persist_directory',
      get label() { return i18n.t('settings:rag.field.chromaPersistDirectory'); },
      get placeholder() { return i18n.t('settings:rag.field.chromaPersistDirectory.placeholder'); },
      defaultValue: 'data/chromadb',
      get helpText() { return i18n.t('settings:rag.field.chromaPersistDirectory.help'); },
      condition: (formData) => formData.vector_store_backend === 'chroma',
    },
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
      name: 'embedding_batch_size',
      get label() { return i18n.t('settings:rag.field.embeddingBatchSize'); },
      min: 1,
      max: 1000,
      defaultValue: 64,
      get helpText() { return i18n.t('settings:rag.field.embeddingBatchSize.help'); }
    },
    {
      type: 'number',
      name: 'embedding_batch_delay_seconds',
      get label() { return i18n.t('settings:rag.field.embeddingBatchDelaySeconds'); },
      min: 0,
      max: 60,
      step: 0.1,
      defaultValue: 0.5,
      get helpText() { return i18n.t('settings:rag.field.embeddingBatchDelaySeconds.help'); }
    },
    {
      type: 'number',
      name: 'embedding_batch_max_retries',
      get label() { return i18n.t('settings:rag.field.embeddingBatchMaxRetries'); },
      min: 0,
      max: 20,
      defaultValue: 3,
      get helpText() { return i18n.t('settings:rag.field.embeddingBatchMaxRetries.help'); }
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
      type: 'checkbox',
      name: 'query_transform_enabled',
      label: 'Enable Query Transform',
      defaultValue: false,
      helpText: 'Rewrite user query before retrieval to improve recall on complex questions.'
    },
    {
      type: 'select',
      name: 'query_transform_mode',
      label: 'Query Transform Mode',
      defaultValue: 'rewrite',
      options: [
        { value: 'none', label: 'None' },
        { value: 'rewrite', label: 'Rewrite' }
      ],
      required: true,
      condition: (formData) => formData.query_transform_enabled === true,
      helpText: 'Current MVP mode supports single-query rewrite.'
    },
    {
      type: 'text',
      name: 'query_transform_model_id',
      label: 'Query Transform Model',
      placeholder: 'auto or provider:model',
      defaultValue: 'auto',
      condition: (formData) => formData.query_transform_enabled === true,
      helpText: 'Use auto to follow the current chat model. Or set a fixed model id.'
    },
    {
      type: 'number',
      name: 'query_transform_timeout_seconds',
      label: 'Query Transform Timeout (s)',
      min: 1,
      max: 30,
      defaultValue: 4,
      required: true,
      condition: (formData) => formData.query_transform_enabled === true,
      helpText: 'If timeout or error occurs, system falls back to the original query.'
    },
    {
      type: 'checkbox',
      name: 'query_transform_guard_enabled',
      label: 'Enable Rewrite Guard',
      defaultValue: true,
      condition: (formData) => formData.query_transform_enabled === true,
      helpText: 'Block unsafe rewrites that add too many unseen terms or drop key constraints.'
    },
    {
      type: 'number',
      name: 'query_transform_guard_max_new_terms',
      label: 'Rewrite Guard Max New Terms',
      min: 0,
      max: 20,
      defaultValue: 2,
      required: true,
      condition: (formData) =>
        formData.query_transform_enabled === true && formData.query_transform_guard_enabled === true,
      helpText: 'If rewritten query introduces more than this number of new key terms, fallback to original.'
    },
    {
      type: 'checkbox',
      name: 'query_transform_crag_enabled',
      label: 'Enable CRAG Quality Gate',
      defaultValue: true,
      condition: (formData) => formData.query_transform_enabled === true,
      helpText: 'Evaluate rewritten-query retrieval quality and fallback to original query when needed.'
    },
    {
      type: 'number',
      name: 'query_transform_crag_lower_threshold',
      label: 'CRAG Lower Threshold',
      min: 0,
      max: 1,
      step: 0.05,
      defaultValue: 0.35,
      required: true,
      condition: (formData) =>
        formData.query_transform_enabled === true && formData.query_transform_crag_enabled === true,
      helpText: 'Below this score, rewritten query is treated as low quality.'
    },
    {
      type: 'number',
      name: 'query_transform_crag_upper_threshold',
      label: 'CRAG Upper Threshold',
      min: 0,
      max: 1,
      step: 0.05,
      defaultValue: 0.75,
      required: true,
      condition: (formData) =>
        formData.query_transform_enabled === true && formData.query_transform_crag_enabled === true,
      helpText: 'Between lower and upper thresholds, rewritten query is ambiguous and compared with original.'
    },
    {
      type: 'select',
      name: 'retrieval_mode',
      get label() { return i18n.t('settings:rag.field.retrievalMode'); },
      defaultValue: 'hybrid',
      get options() {
        return [
          { value: 'vector', label: i18n.t('settings:rag.opt.retrievalVector') },
          { value: 'bm25', label: i18n.t('settings:rag.opt.retrievalBm25') },
          { value: 'hybrid', label: i18n.t('settings:rag.opt.retrievalHybrid') }
        ];
      },
      required: true,
      get helpText() { return i18n.t('settings:rag.field.retrievalMode.help'); }
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
      name: 'vector_recall_k',
      get label() { return i18n.t('settings:rag.field.vectorRecallK'); },
      min: 1,
      max: 500,
      defaultValue: 5,
      required: true,
      condition: (formData) => formData.retrieval_mode !== 'bm25',
      get helpText() { return i18n.t('settings:rag.field.vectorRecallK.help'); }
    },
    {
      type: 'number',
      name: 'bm25_recall_k',
      get label() { return i18n.t('settings:rag.field.bm25RecallK'); },
      min: 1,
      max: 500,
      defaultValue: 20,
      required: true,
      condition: (formData) => formData.retrieval_mode !== 'vector',
      get helpText() { return i18n.t('settings:rag.field.bm25RecallK.help'); }
    },
    {
      type: 'number',
      name: 'bm25_min_term_coverage',
      get label() { return i18n.t('settings:rag.field.bm25MinTermCoverage'); },
      min: 0,
      max: 1,
      step: 0.05,
      defaultValue: 0.35,
      required: true,
      condition: (formData) => formData.retrieval_mode !== 'vector',
      get helpText() { return i18n.t('settings:rag.field.bm25MinTermCoverage.help'); }
    },
    {
      type: 'number',
      name: 'fusion_top_k',
      get label() { return i18n.t('settings:rag.field.fusionTopK'); },
      min: 1,
      max: 500,
      defaultValue: 30,
      required: true,
      condition: (formData) => formData.retrieval_mode === 'hybrid',
      get helpText() { return i18n.t('settings:rag.field.fusionTopK.help'); }
    },
    {
      type: 'select',
      name: 'fusion_strategy',
      get label() { return i18n.t('settings:rag.field.fusionStrategy'); },
      defaultValue: 'rrf',
      options: [
        { value: 'rrf', label: i18n.t('settings:rag.opt.fusionRrf') }
      ],
      required: true,
      condition: (formData) => formData.retrieval_mode === 'hybrid',
      get helpText() { return i18n.t('settings:rag.field.fusionStrategy.help'); }
    },
    {
      type: 'number',
      name: 'rrf_k',
      get label() { return i18n.t('settings:rag.field.rrfK'); },
      min: 1,
      max: 500,
      defaultValue: 40,
      required: true,
      condition: (formData) => formData.retrieval_mode === 'hybrid',
      get helpText() { return i18n.t('settings:rag.field.rrfK.help'); }
    },
    {
      type: 'number',
      name: 'vector_weight',
      get label() { return i18n.t('settings:rag.field.vectorWeight'); },
      min: 0,
      max: 10,
      step: 0.05,
      defaultValue: 0.05,
      required: true,
      condition: (formData) => formData.retrieval_mode === 'hybrid',
      get helpText() { return i18n.t('settings:rag.field.vectorWeight.help'); }
    },
    {
      type: 'number',
      name: 'bm25_weight',
      get label() { return i18n.t('settings:rag.field.bm25Weight'); },
      min: 0,
      max: 10,
      step: 0.1,
      defaultValue: 1,
      required: true,
      condition: (formData) => formData.retrieval_mode === 'hybrid',
      get helpText() { return i18n.t('settings:rag.field.bm25Weight.help'); }
    },
    {
      type: 'number',
      name: 'max_per_doc',
      get label() { return i18n.t('settings:rag.field.maxPerDoc'); },
      min: 0,
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
      defaultValue: 0.65,
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
      type: 'number',
      name: 'context_neighbor_window',
      label: '邻居扩展窗口',
      min: 0,
      max: 10,
      defaultValue: 0,
      required: true,
      helpText: '按 chunk_index 扩展相邻片段。0 表示关闭，2 表示命中后可补前后各 2 段。'
    },
    {
      type: 'number',
      name: 'context_neighbor_max_total',
      label: '邻居扩展上限',
      min: 0,
      max: 200,
      defaultValue: 0,
      required: true,
      helpText: '邻居扩展后的总片段上限（含原始命中）。0 表示按窗口自动估算。'
    },
    {
      type: 'number',
      name: 'context_neighbor_dedup_coverage',
      label: '邻居去重覆盖阈值',
      min: 0.5,
      max: 1,
      step: 0.01,
      defaultValue: 0.9,
      required: true,
      helpText: '候选邻居内容被已选内容覆盖到该比例时会被丢弃，越小去重越激进。'
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
  ],

  transformSave: (data: any) => {
    const rest = { ...data };
    delete rest.retrieval_preset;
    return rest;
  }
};
