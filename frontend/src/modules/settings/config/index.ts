/**
 * Settings Configuration Exports
 *
 * Central export point for all settings page configurations.
 */

// Types
export * from './types';

// CRUD Configs
export { assistantsConfig } from './assistants.config.tsx';
export { modelsConfig } from './models.config.tsx';
export { providersConfig } from './providers.config.tsx';
export { knowledgeBasesConfig } from './knowledgeBases.config.tsx';
export { promptTemplatesConfig } from './promptTemplates.config.tsx';

// Simple Config Configs
export { searchConfig } from './search.config';
export { titleGenerationConfig } from './titleGeneration.config';
export { webpageConfig } from './webpage.config';
export { followupConfig } from './followup.config';
export { compressionConfig } from './compression.config';
export { translationConfig } from './translation.config';
export { ttsConfig } from './tts.config';
export { ragConfig } from './rag.config';
