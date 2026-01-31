/**
 * 模型配置相关的类型定义
 */

// API Protocol types
export type ApiProtocol = 'openai' | 'anthropic' | 'gemini' | 'ollama';

// Provider type (builtin vs custom)
export type ProviderType = 'builtin' | 'custom';

// Model capabilities
export interface ModelCapabilities {
  context_length: number;
  vision: boolean;
  function_calling: boolean;
  reasoning: boolean;
  streaming: boolean;
  file_upload: boolean;
  image_output: boolean;
}

// Default capabilities
export const DEFAULT_CAPABILITIES: ModelCapabilities = {
  context_length: 4096,
  vision: false,
  function_calling: false,
  reasoning: false,
  streaming: true,
  file_upload: false,
  image_output: false,
};

export interface Provider {
  id: string;
  name: string;
  type?: ProviderType;           // builtin or custom
  protocol?: ApiProtocol;        // API protocol type
  base_url: string;
  api_key_env: string;
  api_keys?: string[];           // Multiple keys for rotation
  enabled: boolean;
  has_api_key?: boolean;         // Flag indicating if API key is configured
  api_key?: string;              // Only used in create/update requests

  // Capability declaration (provider-level defaults)
  default_capabilities?: ModelCapabilities;

  // Advanced configuration
  url_suffix?: string;
  auto_append_path?: boolean;
  supports_model_list?: boolean;
  sdk_class?: string;
}

export interface Model {
  id: string;
  name: string;
  provider_id: string;
  group: string;
  temperature: number;
  enabled: boolean;

  // Model capabilities (overrides provider defaults)
  capabilities?: ModelCapabilities;
}

export interface DefaultConfig {
  provider: string;
  model: string;
}

export interface ModelsConfig {
  default: DefaultConfig;
  providers: Provider[];
  models: Model[];
}

// Builtin provider info (from /api/models/providers/builtin)
export interface BuiltinProviderInfo {
  id: string;
  name: string;
  protocol: string;
  base_url: string;
  api_key_env: string;
  sdk_class: string;
  supports_model_list: boolean;
  default_capabilities: ModelCapabilities;
  builtin_models: { id: string; name: string }[];
}

// Model info (from fetch models API)
export interface ModelInfo {
  id: string;
  name: string;
}

// Capabilities response
export interface CapabilitiesResponse {
  model_id: string;
  provider_id: string;
  capabilities: ModelCapabilities;
}

// Protocol info
export interface ProtocolInfo {
  id: ApiProtocol;
  name: string;
  description: string;
}
