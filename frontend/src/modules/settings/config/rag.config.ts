/**
 * RAG Settings Configuration
 *
 * Defines the structure and behavior of the RAG settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';

export const ragConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  title: 'RAG Settings',
  description: 'Configure Retrieval-Augmented Generation (embedding, chunking, and retrieval)',

  apiEndpoint: {
    get: '/api/rag/config',
    update: '/api/rag/config'
  },

  fields: [
    {
      type: 'select',
      name: 'embedding_provider',
      label: 'Embedding Provider',
      required: true,
      defaultValue: 'api',
      options: [
        {
          value: 'api',
          label: 'API-based (uses configured LLM provider)'
        },
        {
          value: 'local',
          label: 'Local (sentence-transformers, requires install)'
        }
      ],
      helpText: 'Select the embedding provider for vector generation'
    },
    {
      type: 'text',
      name: 'embedding_api_model',
      label: 'API Embedding Model',
      placeholder: 'e.g., jina-embeddings-v3 or provider:model',
      defaultValue: 'jina-embeddings-v3',
      helpText: 'Model name for embeddings. Use provider:model format to fall back to LLM provider config.',
      condition: (formData) => formData.embedding_provider === 'api',
    },
    {
      type: 'text',
      name: 'embedding_api_base_url',
      label: 'Embedding API Base URL',
      placeholder: 'e.g., https://api.jina.ai/v1',
      defaultValue: '',
      helpText: 'Base URL for the embedding API. Leave empty to use LLM provider base URL.',
      condition: (formData) => formData.embedding_provider === 'api',
    },
    {
      type: 'password',
      name: 'embedding_api_key',
      label: 'Embedding API Key',
      placeholder: 'Enter API key for embedding service',
      defaultValue: '',
      helpText: 'API key for the embedding service. Leave empty to use LLM provider API key.',
      condition: (formData) => formData.embedding_provider === 'api',
    },
    {
      type: 'text',
      name: 'embedding_local_model',
      label: 'Local Model Name',
      placeholder: 'e.g., all-MiniLM-L6-v2',
      defaultValue: 'all-MiniLM-L6-v2',
      helpText: 'HuggingFace model name for local embeddings',
      condition: (formData) => formData.embedding_provider === 'local',
    },
    {
      type: 'select',
      name: 'embedding_local_device',
      label: 'Local Device',
      defaultValue: 'cpu',
      options: [
        { value: 'cpu', label: 'CPU' },
        { value: 'cuda', label: 'CUDA (GPU)' }
      ],
      helpText: 'Device for running local embedding model',
      condition: (formData) => formData.embedding_provider === 'local',
    },
    {
      type: 'number',
      name: 'chunk_size',
      label: 'Default Chunk Size',
      min: 100,
      max: 10000,
      defaultValue: 1000,
      required: true,
      helpText: 'Default size for text chunks (characters)'
    },
    {
      type: 'number',
      name: 'chunk_overlap',
      label: 'Default Chunk Overlap',
      min: 0,
      max: 5000,
      defaultValue: 200,
      required: true,
      helpText: 'Default overlap between adjacent chunks (characters)'
    },
    {
      type: 'number',
      name: 'top_k',
      label: 'Top K Results',
      min: 1,
      max: 50,
      defaultValue: 5,
      required: true,
      helpText: 'Number of top results to retrieve from knowledge base'
    },
    {
      type: 'number',
      name: 'score_threshold',
      label: 'Score Threshold',
      min: 0,
      max: 1,
      step: 0.05,
      defaultValue: 0.3,
      required: true,
      helpText: 'Minimum similarity score for results (0-1)'
    }
  ]
};
