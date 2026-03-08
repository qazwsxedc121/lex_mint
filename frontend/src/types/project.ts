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

export interface ProjectToolCatalogResponse {
  groups: ProjectToolCatalogGroup[];
  tools: ProjectToolCatalogItem[];
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
