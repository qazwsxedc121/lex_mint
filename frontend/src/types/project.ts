// Project Management Types

export interface Project {
  id: string;
  name: string;
  root_path: string;
  description?: string;
  settings: ProjectSettings;
  created_at: string;
  updated_at: string;
}

export interface ProjectRagSettings {
  knowledge_base_ids: string[];
  knowledge_base_mode: 'append' | 'override';
}

export interface ProjectToolSettings {
  tool_enabled_map: Record<string, boolean>;
}

export interface ProjectToolCatalogItem {
  name: string;
  description: string;
  group: string;
  source: string;
  plugin_id?: string | null;
  plugin_name?: string | null;
  plugin_version?: string | null;
  enabled_by_default: boolean;
  title_i18n_key: string;
  description_i18n_key: string;
  requires_project_knowledge: boolean;
}

export interface ProjectToolCatalogGroup {
  key: string;
  title_i18n_key: string;
  description_i18n_key: string;
  tools: ProjectToolCatalogItem[];
}

export interface ProjectChatCapabilityItem {
  control_type?: 'toggle' | 'select';
  arg_key?: string;
  options?: Array<{
    value: string;
    label_i18n_key: string;
    description_i18n_key?: string | null;
  }>;
  default_value?: string | null;
  id: string;
  plugin_id: string;
  plugin_name?: string | null;
  plugin_version?: string | null;
  title_i18n_key: string;
  description_i18n_key: string;
  icon?: string | null;
  order: number;
  default_enabled: boolean;
  visible_in_input: boolean;
}

export interface ProjectToolCatalogResponse {
  groups: ProjectToolCatalogGroup[];
  tools: ProjectToolCatalogItem[];
  chat_capabilities: ProjectChatCapabilityItem[];
}

export interface ProjectSettings {
  rag: ProjectRagSettings;
  tools: ProjectToolSettings;
}

export interface ProjectCreate {
  name: string;
  root_path: string;
  description?: string;
  settings?: ProjectSettings;
}

export interface ProjectUpdate {
  name?: string;
  root_path?: string;
  description?: string;
  settings?: ProjectSettings;
}

export interface DirectoryEntry {
  name: string;
  path: string;
  is_dir: boolean;
}

export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  modified_at?: string;
  children?: FileNode[];
}

export interface FileContent {
  path: string;
  content: string;
  content_hash?: string;
  encoding: string;
  size: number;
  mime_type: string;
}

export interface FileRenameRequest {
  source_path: string;
  target_path: string;
}

export interface FileRenameResult {
  old_path: string;
  new_path: string;
  type: 'file' | 'directory';
  size?: number;
  modified_at?: string;
}
