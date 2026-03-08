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

export interface ProjectSettings {
  rag: ProjectRagSettings;
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
