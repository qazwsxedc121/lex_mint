// Project Management Types

export interface Project {
  id: string;
  name: string;
  root_path: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  root_path: string;
  description?: string;
}

export interface ProjectUpdate {
  name?: string;
  root_path?: string;
  description?: string;
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
  encoding: string;
  size: number;
  mime_type: string;
}
