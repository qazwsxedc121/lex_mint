/**
 * Compression Settings Configuration
 *
 * Defines the structure and behavior of the Context Compression settings page.
 */

import type { SimpleConfigSettingsConfig } from './types';
import i18n from '../../../i18n';

export const compressionConfig: SimpleConfigSettingsConfig = {
  type: 'config',
  get title() { return i18n.t('settings:compression.title'); },
  get description() { return i18n.t('settings:compression.description'); },

  apiEndpoint: {
    get: '/api/compression/config',
    update: '/api/compression/config'
  },

  fields: [
    {
      type: 'select',
      name: 'provider',
      get label() { return i18n.t('settings:compression.field.provider'); },
      required: true,
      defaultValue: 'model_config',
      get options() {
        return [
          { value: 'model_config', label: i18n.t('settings:compression.opt.modelConfig') },
          { value: 'local_gguf', label: i18n.t('settings:compression.opt.localGguf') },
        ];
      },
      get helpText() { return i18n.t('settings:compression.field.provider.help'); }
    },
    {
      type: 'checkbox',
      name: 'auto_compress_enabled',
      get label() { return i18n.t('settings:compression.field.autoCompress'); },
      defaultValue: false
    },
    {
      type: 'select',
      name: 'compression_output_language',
      get label() { return i18n.t('settings:compression.field.outputLanguage'); },
      defaultValue: 'auto',
      options: [
        { value: 'auto', label: i18n.t('settings:compression.opt.outputLanguageAuto') },
        { value: 'none', label: i18n.t('settings:compression.opt.outputLanguageNone') },
        { value: 'zh', label: i18n.t('settings:compression.opt.outputLanguageZh') },
        { value: 'en', label: i18n.t('settings:compression.opt.outputLanguageEn') },
        { value: 'ja', label: i18n.t('settings:compression.opt.outputLanguageJa') },
        { value: 'ko', label: i18n.t('settings:compression.opt.outputLanguageKo') },
        { value: 'fr', label: i18n.t('settings:compression.opt.outputLanguageFr') },
        { value: 'de', label: i18n.t('settings:compression.opt.outputLanguageDe') },
        { value: 'es', label: i18n.t('settings:compression.opt.outputLanguageEs') },
        { value: 'ru', label: i18n.t('settings:compression.opt.outputLanguageRu') },
        { value: 'pt', label: i18n.t('settings:compression.opt.outputLanguagePt') },
      ],
      get helpText() { return i18n.t('settings:compression.field.outputLanguage.help'); },
    },
    {
      type: 'slider',
      name: 'auto_compress_threshold',
      get label() { return i18n.t('settings:compression.field.threshold'); },
      min: 0.1,
      max: 0.9,
      step: 0.05,
      defaultValue: 0.5,
      get helpText() { return i18n.t('settings:compression.field.threshold.help'); },
      condition: (formData) => formData.auto_compress_enabled === true
    },
    {
      type: 'select',
      name: 'model_id',
      get label() { return i18n.t('settings:compression.field.modelId'); },
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        const modelOptions = models.map((m: any) => ({
          value: `${m.provider_id}:${m.id}`,
          label: m.name || m.id
        }));
        return [
          { value: 'same_as_chat', label: i18n.t('settings:compression.opt.sameAsChatModel') },
          ...modelOptions,
        ];
      },
      get helpText() { return i18n.t('settings:compression.field.modelId.help'); },
      condition: (formData) => formData.provider !== 'local_gguf',
    },
    {
      type: 'text',
      name: 'local_gguf_model_path',
      get label() { return i18n.t('settings:compression.field.localGgufModelPath'); },
      get placeholder() { return i18n.t('settings:compression.field.localGgufModelPath.placeholder'); },
      defaultValue: 'models/llm/local-summarizer.gguf',
      get helpText() { return i18n.t('settings:compression.field.localGgufModelPath.help'); },
      condition: (formData) => formData.provider === 'local_gguf',
    },
    {
      type: 'number',
      name: 'local_gguf_n_ctx',
      get label() { return i18n.t('settings:compression.field.localGgufCtx'); },
      min: 512,
      max: 65536,
      defaultValue: 8192,
      get helpText() { return i18n.t('settings:compression.field.localGgufCtx.help'); },
      condition: (formData) => formData.provider === 'local_gguf',
    },
    {
      type: 'number',
      name: 'local_gguf_n_threads',
      get label() { return i18n.t('settings:compression.field.localGgufThreads'); },
      min: 0,
      max: 256,
      defaultValue: 0,
      get helpText() { return i18n.t('settings:compression.field.localGgufThreads.help'); },
      condition: (formData) => formData.provider === 'local_gguf',
    },
    {
      type: 'number',
      name: 'local_gguf_n_gpu_layers',
      get label() { return i18n.t('settings:compression.field.localGgufGpuLayers'); },
      min: 0,
      max: 1024,
      defaultValue: 0,
      get helpText() { return i18n.t('settings:compression.field.localGgufGpuLayers.help'); },
      condition: (formData) => formData.provider === 'local_gguf',
    },
    {
      type: 'number',
      name: 'local_gguf_max_tokens',
      get label() { return i18n.t('settings:compression.field.localGgufMaxTokens'); },
      min: 64,
      max: 16384,
      defaultValue: 2048,
      get helpText() { return i18n.t('settings:compression.field.localGgufMaxTokens.help'); },
      condition: (formData) => formData.provider === 'local_gguf',
    },
    {
      type: 'select',
      name: 'compression_strategy',
      get label() { return i18n.t('settings:compression.field.strategy'); },
      defaultValue: 'hierarchical',
      options: [
        { value: 'hierarchical', label: i18n.t('settings:compression.opt.hierarchical') },
        { value: 'single_pass', label: i18n.t('settings:compression.opt.singlePass') },
      ],
      get helpText() { return i18n.t('settings:compression.field.strategy.help'); },
      condition: (formData) => formData.provider === 'local_gguf',
    },
    {
      type: 'number',
      name: 'hierarchical_chunk_target_tokens',
      get label() { return i18n.t('settings:compression.field.hierChunkTargetTokens'); },
      min: 0,
      max: 8192,
      defaultValue: 0,
      get helpText() { return i18n.t('settings:compression.field.hierChunkTargetTokens.help'); },
      condition: (formData) => formData.provider === 'local_gguf' && formData.compression_strategy === 'hierarchical',
    },
    {
      type: 'number',
      name: 'hierarchical_chunk_overlap_messages',
      get label() { return i18n.t('settings:compression.field.hierChunkOverlapMessages'); },
      min: 0,
      max: 20,
      defaultValue: 2,
      get helpText() { return i18n.t('settings:compression.field.hierChunkOverlapMessages.help'); },
      condition: (formData) => formData.provider === 'local_gguf' && formData.compression_strategy === 'hierarchical',
    },
    {
      type: 'number',
      name: 'hierarchical_reduce_target_tokens',
      get label() { return i18n.t('settings:compression.field.hierReduceTargetTokens'); },
      min: 0,
      max: 16384,
      defaultValue: 0,
      get helpText() { return i18n.t('settings:compression.field.hierReduceTargetTokens.help'); },
      condition: (formData) => formData.provider === 'local_gguf' && formData.compression_strategy === 'hierarchical',
    },
    {
      type: 'number',
      name: 'hierarchical_reduce_overlap_items',
      get label() { return i18n.t('settings:compression.field.hierReduceOverlapItems'); },
      min: 0,
      max: 10,
      defaultValue: 1,
      get helpText() { return i18n.t('settings:compression.field.hierReduceOverlapItems.help'); },
      condition: (formData) => formData.provider === 'local_gguf' && formData.compression_strategy === 'hierarchical',
    },
    {
      type: 'number',
      name: 'hierarchical_max_levels',
      get label() { return i18n.t('settings:compression.field.hierMaxLevels'); },
      min: 1,
      max: 8,
      defaultValue: 4,
      get helpText() { return i18n.t('settings:compression.field.hierMaxLevels.help'); },
      condition: (formData) => formData.provider === 'local_gguf' && formData.compression_strategy === 'hierarchical',
    },
    {
      type: 'checkbox',
      name: 'quality_guard_enabled',
      get label() { return i18n.t('settings:compression.field.qualityGuardEnabled'); },
      defaultValue: true,
      condition: (formData) => formData.provider === 'local_gguf',
    },
    {
      type: 'slider',
      name: 'quality_guard_min_coverage',
      get label() { return i18n.t('settings:compression.field.qualityGuardMinCoverage'); },
      min: 0.5,
      max: 1.0,
      step: 0.05,
      defaultValue: 0.75,
      get helpText() { return i18n.t('settings:compression.field.qualityGuardMinCoverage.help'); },
      condition: (formData) => formData.provider === 'local_gguf' && formData.quality_guard_enabled !== false,
    },
    {
      type: 'number',
      name: 'quality_guard_max_facts',
      get label() { return i18n.t('settings:compression.field.qualityGuardMaxFacts'); },
      min: 5,
      max: 100,
      defaultValue: 24,
      get helpText() { return i18n.t('settings:compression.field.qualityGuardMaxFacts.help'); },
      condition: (formData) => formData.provider === 'local_gguf' && formData.quality_guard_enabled !== false,
    },
    {
      type: 'checkbox',
      name: 'compression_metrics_enabled',
      get label() { return i18n.t('settings:compression.field.metricsEnabled'); },
      defaultValue: true,
      get helpText() { return i18n.t('settings:compression.field.metricsEnabled.help'); },
    },
    {
      type: 'slider',
      name: 'temperature',
      get label() { return i18n.t('settings:compression.field.temperature'); },
      min: 0,
      max: 2,
      step: 0.1,
      defaultValue: 0.3,
      get helpText() { return i18n.t('settings:compression.field.temperature.help'); }
    },
    {
      type: 'number',
      name: 'min_messages',
      get label() { return i18n.t('settings:compression.field.minMessages'); },
      min: 1,
      max: 50,
      defaultValue: 2,
      required: true,
      get helpText() { return i18n.t('settings:compression.field.minMessages.help'); }
    },
    {
      type: 'number',
      name: 'timeout_seconds',
      get label() { return i18n.t('settings:compression.field.timeout'); },
      min: 10,
      max: 300,
      defaultValue: 60,
      required: true,
      get helpText() { return i18n.t('settings:compression.field.timeout.help'); }
    },
    {
      type: 'textarea',
      name: 'prompt_template',
      get label() { return i18n.t('settings:compression.field.promptTemplate'); },
      rows: 10,
      monospace: true,
      get placeholder() { return i18n.t('settings:compression.field.promptTemplate.placeholder'); },
      get helpText() { return i18n.t('settings:compression.field.promptTemplate.help'); }
    }
  ]
};
