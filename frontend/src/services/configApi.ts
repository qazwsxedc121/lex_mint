import { api } from './apiClient';

export interface SearchConfig {
  provider: string;
  max_results: number;
  timeout_seconds: number;
}

export interface SearchConfigUpdate {
  provider?: string;
  max_results?: number;
  timeout_seconds?: number;
}

/**
 * Get search configuration
 */
export async function getSearchConfig(): Promise<SearchConfig> {
  const response = await api.get<SearchConfig>('/api/search/config');
  return response.data;
}

/**
 * Update search configuration
 */
export async function updateSearchConfig(updates: SearchConfigUpdate): Promise<void> {
  await api.put('/api/search/config', updates);
}

export interface WebpageConfig {
  enabled: boolean;
  max_urls: number;
  timeout_seconds: number;
  max_bytes: number;
  max_content_chars: number;
  user_agent: string;
  proxy?: string | null;
  trust_env: boolean;
  diagnostics_enabled: boolean;
  diagnostics_timeout_seconds: number;
}

export interface WebpageConfigUpdate {
  enabled?: boolean;
  max_urls?: number;
  timeout_seconds?: number;
  max_bytes?: number;
  max_content_chars?: number;
  user_agent?: string;
  proxy?: string | null;
  trust_env?: boolean;
  diagnostics_enabled?: boolean;
  diagnostics_timeout_seconds?: number;
}

/**
 * Get webpage configuration
 */
export async function getWebpageConfig(): Promise<WebpageConfig> {
  const response = await api.get<WebpageConfig>('/api/webpage/config');
  return response.data;
}

/**
 * Update webpage configuration
 */
export async function updateWebpageConfig(updates: WebpageConfigUpdate): Promise<void> {
  await api.put('/api/webpage/config', updates);
}

export interface TitleGenerationConfig {
  enabled: boolean;
  trigger_threshold: number;
  model_id: string;
  prompt_template: string;
  max_context_rounds: number;
  timeout_seconds: number;
}

export interface TitleGenerationConfigUpdate {
  enabled?: boolean;
  trigger_threshold?: number;
  model_id?: string;
  prompt_template?: string;
  max_context_rounds?: number;
  timeout_seconds?: number;
}

export interface CodeExecutionConfig {
  enable_client_tool_execution: boolean;
  enable_server_jupyter_execution: boolean;
  enable_server_subprocess_execution: boolean;
  execution_priority: Array<'client' | 'server_jupyter' | 'server_subprocess'>;
  jupyter_kernel_name: string;
  // Legacy compatibility fields
  enable_server_side_tool_execution?: boolean;
  server_side_execution_backend?: 'subprocess' | 'jupyter';
}

export interface CodeExecutionConfigUpdate {
  enable_client_tool_execution?: boolean;
  enable_server_jupyter_execution?: boolean;
  enable_server_subprocess_execution?: boolean;
  execution_priority?: Array<'client' | 'server_jupyter' | 'server_subprocess'>;
  jupyter_kernel_name?: string;
}

export interface ToolGateRule {
  id: string;
  enabled: boolean;
  priority: number;
  pattern: string;
  flags: string;
  include_tools: string[];
  exclude_tools: string[];
  description?: string | null;
}

export interface ToolGateConfig {
  enabled: boolean;
  rules: ToolGateRule[];
}

export interface ToolGateConfigUpdate {
  enabled?: boolean;
  rules?: ToolGateRule[];
}

export interface ToolDescriptionItem {
  name: string;
  group: string;
  source: string;
  default_description: string;
  override_description?: string | null;
  effective_description: string;
  title_i18n_key: string;
  description_i18n_key: string;
}

export interface ToolDescriptionsConfig {
  tools: ToolDescriptionItem[];
}

export interface ToolDescriptionsUpdate {
  overrides: Record<string, string | null>;
}

export async function getCodeExecutionConfig(): Promise<CodeExecutionConfig> {
  const response = await api.get<CodeExecutionConfig>('/api/code-execution/config');
  return response.data;
}

export async function updateCodeExecutionConfig(
  updates: CodeExecutionConfigUpdate
): Promise<void> {
  await api.put('/api/code-execution/config', updates);
}

export async function getToolGateConfig(): Promise<ToolGateConfig> {
  const response = await api.get<ToolGateConfig>('/api/tool-gate/config');
  return response.data;
}

export async function updateToolGateConfig(updates: ToolGateConfigUpdate): Promise<void> {
  await api.put('/api/tool-gate/config', updates);
}

export async function getToolDescriptionsConfig(): Promise<ToolDescriptionsConfig> {
  const response = await api.get<ToolDescriptionsConfig>('/api/tools/descriptions');
  return response.data;
}

export async function updateToolDescriptionsConfig(
  updates: ToolDescriptionsUpdate
): Promise<void> {
  await api.put('/api/tools/descriptions', updates);
}

/**
 * Get title generation configuration
 */
export async function getTitleGenerationConfig(): Promise<TitleGenerationConfig> {
  const response = await api.get<TitleGenerationConfig>('/api/title-generation/config');
  return response.data;
}

/**
 * Update title generation configuration
 */
export async function updateTitleGenerationConfig(updates: TitleGenerationConfigUpdate): Promise<void> {
  await api.put('/api/title-generation/config', updates);
}

/**
 * Manually trigger title generation for a session
 */
export async function generateTitleManually(
  sessionId: string,
  contextType: string = 'chat',
  projectId?: string,
): Promise<{ message: string; title: string }> {
  const params = new URLSearchParams();
  params.append('context_type', contextType);
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await api.post<{ message: string; title: string }>(`/api/title-generation/generate?${params.toString()}`, {
    session_id: sessionId,
  });
  return response.data;
}
