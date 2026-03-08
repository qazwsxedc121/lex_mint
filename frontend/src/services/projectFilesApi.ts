import { api } from './apiClient';

import type { DirectoryEntry, FileContent, FileNode, FileRenameResult } from '../types/project';

/**
 * File search result with proximity scoring.
 */
export interface FileSearchResult {
  path: string;
  name: string;
  directory: string;
  extension: string;
  score: number;
  proximityReason: 'same-dir' | 'child-dir' | 'parent-dir' | 'sibling' | 'project-wide' | 'no-match';
}

export interface ProjectTextSearchMatch {
  file_path: string;
  line_number: number;
  line_text: string;
  context_before: string[];
  context_after: string[];
}

export interface ProjectTextSearchResponse {
  ok: boolean;
  query: string;
  case_sensitive: boolean;
  use_regex: boolean;
  include_glob?: string | null;
  exclude_glob?: string | null;
  max_results: number;
  results_count: number;
  truncated: boolean;
  scan_limit_hit: boolean;
  scanned_files: number;
  skipped_hidden_files: number;
  skipped_binary_files: number;
  skipped_large_files: number;
  results: ProjectTextSearchMatch[];
}

export type ProjectWorkspaceItemType = 'file' | 'session' | 'run';

export interface ProjectWorkspaceRecentItem {
  type: ProjectWorkspaceItemType;
  id: string;
  title: string;
  path?: string | null;
  updated_at?: string | null;
  meta: Record<string, unknown>;
}

export interface ProjectWorkspaceState {
  version: number;
  project_id: string;
  updated_at?: string | null;
  recent_items: ProjectWorkspaceRecentItem[];
  extra: Record<string, unknown>;
}

export interface ProjectWorkspaceItemUpsertRequest {
  type: ProjectWorkspaceItemType;
  id: string;
  title: string;
  path?: string;
  updated_at?: string;
  meta?: Record<string, unknown>;
}

export interface ApplyProjectChatDiffRequest {
  session_id: string;
  pending_patch_id: string;
  expected_hash?: string;
}

export interface ApplyProjectChatDiffResponse {
  ok: boolean;
  file_path: string;
  new_content_hash: string;
  updated_at: number;
  content: string;
}

/**
 * Get file tree for a project
 */
export async function getFileTree(id: string, path?: string): Promise<FileNode> {
  const url = path ? `/api/projects/${id}/tree?path=${encodeURIComponent(path)}` : `/api/projects/${id}/tree`;
  const response = await api.get<FileNode>(url);
  return response.data;
}

/**
 * Create a new file in a project
 */
export async function createFile(
  id: string,
  path: string,
  content: string = '',
  encoding: string = 'utf-8',
): Promise<FileContent> {
  const response = await api.post<FileContent>(`/api/projects/${id}/files`, {
    path,
    content,
    encoding,
  });
  return response.data;
}

/**
 * Create a new folder in a project
 */
export async function createFolder(id: string, path: string): Promise<FileNode> {
  const response = await api.post<FileNode>(`/api/projects/${id}/directories`, {
    path,
  });
  return response.data;
}

/**
 * Delete a folder from a project
 */
export async function deleteFolder(id: string, path: string, recursive: boolean = false): Promise<void> {
  await api.delete(`/api/projects/${id}/directories`, {
    params: {
      path,
      recursive,
    },
  });
}

/**
 * Delete a file from a project
 */
export async function deleteFile(id: string, path: string): Promise<void> {
  await api.delete(`/api/projects/${id}/files`, {
    params: {
      path,
    },
  });
}

/**
 * Read file content from a project
 */
export async function readFile(id: string, path: string): Promise<FileContent> {
  const response = await api.get<FileContent>(`/api/projects/${id}/files?path=${encodeURIComponent(path)}`);
  return response.data;
}

/**
 * Write content to a file in a project
 */
export async function writeFile(
  id: string,
  path: string,
  content: string,
  encoding: string = 'utf-8',
  expectedHash?: string,
): Promise<FileContent> {
  const response = await api.put<FileContent>(`/api/projects/${id}/files`, {
    path,
    content,
    encoding,
    expected_hash: expectedHash,
  });
  return response.data;
}

export async function applyProjectChatDiff(
  id: string,
  payload: ApplyProjectChatDiffRequest,
): Promise<ApplyProjectChatDiffResponse> {
  const response = await api.post<ApplyProjectChatDiffResponse>(
    `/api/projects/${id}/chat/apply-diff`,
    payload,
  );
  return response.data;
}

/**
 * Rename or move a file or directory in a project
 */
export async function renameProjectPath(id: string, sourcePath: string, targetPath: string): Promise<FileRenameResult> {
  const response = await api.put<FileRenameResult>(`/api/projects/${id}/paths/rename`, {
    source_path: sourcePath,
    target_path: targetPath,
  });
  return response.data;
}

/**
 * Search project files with proximity-based scoring
 */
export async function searchProjectFiles(
  projectId: string,
  query: string,
  currentFile?: string | null,
): Promise<FileSearchResult[]> {
  const params = new URLSearchParams({ query });
  if (currentFile) {
    params.append('current_file', currentFile);
  }

  const response = await api.get<FileSearchResult[]>(
    `/api/projects/${projectId}/files/search?${params}`,
  );
  return response.data;
}

export async function searchProjectText(
  projectId: string,
  query: string,
  options?: {
    caseSensitive?: boolean;
    useRegex?: boolean;
    includeGlob?: string;
    excludeGlob?: string;
    maxResults?: number;
    contextLines?: number;
    maxCharsPerLine?: number;
  },
): Promise<ProjectTextSearchResponse> {
  const params = new URLSearchParams({ query });
  if (options?.caseSensitive) {
    params.append('case_sensitive', 'true');
  }
  if (options?.useRegex) {
    params.append('use_regex', 'true');
  }
  if (options?.includeGlob) {
    params.append('include_glob', options.includeGlob);
  }
  if (options?.excludeGlob) {
    params.append('exclude_glob', options.excludeGlob);
  }
  if (typeof options?.maxResults === 'number') {
    params.append('max_results', String(options.maxResults));
  }
  if (typeof options?.contextLines === 'number') {
    params.append('context_lines', String(options.contextLines));
  }
  if (typeof options?.maxCharsPerLine === 'number') {
    params.append('max_chars_per_line', String(options.maxCharsPerLine));
  }

  const response = await api.get<ProjectTextSearchResponse>(
    `/api/projects/${projectId}/text/search?${params.toString()}`,
  );
  return response.data;
}

export async function getProjectWorkspaceState(projectId: string): Promise<ProjectWorkspaceState> {
  const response = await api.get<ProjectWorkspaceState>(`/api/projects/${projectId}/workspace-state`);
  return response.data;
}

export async function addProjectWorkspaceItem(
  projectId: string,
  payload: ProjectWorkspaceItemUpsertRequest,
): Promise<ProjectWorkspaceState> {
  const response = await api.post<ProjectWorkspaceState>(`/api/projects/${projectId}/workspace-state/items`, payload);
  return response.data;
}

export async function listProjectBrowseRoots(): Promise<DirectoryEntry[]> {
  const response = await api.get<DirectoryEntry[]>('/api/projects/browse/roots');
  return response.data;
}

export async function listProjectDirectories(path: string): Promise<DirectoryEntry[]> {
  const params = new URLSearchParams({ path });
  const response = await api.get<DirectoryEntry[]>(`/api/projects/browse?${params.toString()}`);
  return response.data;
}

export async function createProjectBrowseDirectory(parentPath: string, name: string): Promise<DirectoryEntry> {
  const response = await api.post<DirectoryEntry>('/api/projects/browse/directories', {
    parent_path: parentPath,
    name,
  });
  return response.data;
}