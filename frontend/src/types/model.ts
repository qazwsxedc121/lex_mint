/**
 * 模型配置相关的类型定义
 */

// API Protocol types
export type ApiProtocol = 'openai' | 'anthropic' | 'gemini' | 'ollama';

// Provider call mode
export type CallMode = 'auto' | 'native' | 'chat_completions' | 'responses';

// Provider type (builtin vs custom)
export type ProviderType = 'builtin' | 'custom';

// Model capabilities
export type ReasoningControlMode = 'toggle' | 'enum' | 'budget';

export interface ReasoningControls {
  mode: ReasoningControlMode;
  param: string;
  options: string[];
  default_option?: string | null;
  disable_supported: boolean;
}

export interface ModelCapabilities {
  context_length: number;
  vision: boolean;
  function_calling: boolean;
  reasoning: boolean;
  reasoning_controls?: ReasoningControls | null;
  requires_interleaved_thinking: boolean;
  streaming: boolean;
  file_upload: boolean;
  image_output: boolean;
}

export interface EndpointProfile {
  id: string;
  label: string;
  base_url: string;
  region_tags: string[];
  priority: number;
  probe_method: string;
}

export interface ChatTemplate {
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  top_k?: number;
  frequency_penalty?: number;
  presence_penalty?: number;
}

// Default capabilities
export const DEFAULT_CAPABILITIES: ModelCapabilities = {
  context_length: 4096,
  vision: false,
  function_calling: false,
  reasoning: false,
  reasoning_controls: null,
  requires_interleaved_thinking: false,
  streaming: true,
  file_upload: false,
  image_output: false,
};

export interface Provider {
  id: string;
  name: string;
  type?: ProviderType;           // builtin or custom
  protocol?: ApiProtocol;        // API protocol type
  call_mode?: CallMode;          // Call mode within adapter family
  base_url: string;
  endpoint_profile_id?: string | null;
  endpoint_profiles?: EndpointProfile[];
  api_keys?: string[];           // Multiple keys for rotation
  enabled: boolean;
  has_api_key?: boolean;         // Flag indicating if API key is configured
  requires_api_key?: boolean;    // Whether API key is required
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
  tags: string[];
  enabled: boolean;

  // Model capabilities (overrides provider defaults)
  capabilities?: ModelCapabilities;
  chat_template?: ChatTemplate;
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
  sdk_class: string;
  supports_model_list: boolean;
  default_capabilities: ModelCapabilities;
  endpoint_profiles: EndpointProfile[];
  default_endpoint_profile_id?: string | null;
}

// Model info (from fetch models API)
export interface ModelInfo {
  id: string;
  name: string;
  capabilities?: ModelCapabilities;
  tags?: string[];
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

export interface ProviderEndpointProbeRequest {
  mode?: 'auto' | 'manual';
  endpoint_profile_id?: string;
  base_url_override?: string;
  use_stored_key?: boolean;
  api_key?: string;
  model_id?: string;
  strict?: boolean;
  client_region_hint?: 'cn' | 'global' | 'unknown';
}

export interface ProviderEndpointProbeResult {
  endpoint_profile_id?: string | null;
  label: string;
  base_url: string;
  success: boolean;
  classification: string;
  http_status?: number | null;
  latency_ms?: number | null;
  message: string;
  detected_model_count?: number | null;
  priority: number;
  region_tags: string[];
}

export interface ProviderEndpointProbeResponse {
  provider_id: string;
  results: ProviderEndpointProbeResult[];
  recommended_endpoint_profile_id?: string | null;
  recommended_base_url?: string | null;
  summary: string;
}

export interface ProviderEndpointProfilesResponse {
  provider_id: string;
  current_endpoint_profile_id?: string | null;
  current_base_url: string;
  endpoint_profiles: EndpointProfile[];
  recommended_endpoint_profile_id?: string | null;
}
