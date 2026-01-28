/**
 * 模型配置相关的类型定义
 */

export interface Provider {
  id: string;
  name: string;
  base_url: string;
  api_key_env: string;
  enabled: boolean;
  has_api_key?: boolean;  // Flag indicating if API key is configured
  api_key?: string;       // Only used in create/update requests, never in responses
}

export interface Model {
  id: string;
  name: string;
  provider_id: string;
  group: string;
  temperature: number;
  enabled: boolean;
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
