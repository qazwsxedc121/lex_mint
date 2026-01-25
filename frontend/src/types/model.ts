/**
 * 模型配置相关的类型定义
 */

export interface Provider {
  id: string;
  name: string;
  base_url: string;
  api_key_env: string;
  enabled: boolean;
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
