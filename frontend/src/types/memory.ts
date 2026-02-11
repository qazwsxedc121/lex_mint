/**
 * Memory type definitions
 */

export type MemoryScope = 'global' | 'assistant';

export interface MemorySettings {
  enabled: boolean;
  profile_id: string;
  collection_name: string;
  enabled_layers: string[];
  top_k: number;
  score_threshold: number;
  max_injected_items: number;
  max_item_length: number;
  auto_extract_enabled: boolean;
  min_text_length: number;
  max_items_per_turn: number;
  global_enabled: boolean;
  assistant_enabled: boolean;
}

export interface MemorySettingsUpdate {
  enabled?: boolean;
  profile_id?: string;
  collection_name?: string;
  enabled_layers?: string[];
  top_k?: number;
  score_threshold?: number;
  max_injected_items?: number;
  max_item_length?: number;
  auto_extract_enabled?: boolean;
  min_text_length?: number;
  max_items_per_turn?: number;
  global_enabled?: boolean;
  assistant_enabled?: boolean;
}

export interface MemoryItem {
  id: string;
  content: string;
  score?: number | null;
  profile_id?: string;
  scope?: MemoryScope;
  assistant_id?: string | null;
  layer?: string;
  confidence?: number;
  importance?: number;
  source_session_id?: string | null;
  source_message_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_hit_at?: string | null;
  hit_count?: number;
  is_active?: boolean;
  pinned?: boolean;
  hash?: string | null;
}

export interface MemoryListResponse {
  items: MemoryItem[];
  count: number;
}

export interface MemoryCreateRequest {
  content: string;
  scope: MemoryScope;
  layer: string;
  assistant_id?: string;
  profile_id?: string;
  confidence?: number;
  importance?: number;
  source_session_id?: string;
  source_message_id?: string;
  pinned?: boolean;
}

export interface MemoryUpdateRequest {
  content?: string;
  scope?: MemoryScope;
  layer?: string;
  assistant_id?: string;
  confidence?: number;
  importance?: number;
  pinned?: boolean;
  is_active?: boolean;
}

export interface MemorySearchRequest {
  query: string;
  profile_id?: string;
  assistant_id?: string;
  scope?: MemoryScope;
  layer?: string;
  include_global?: boolean;
  include_assistant?: boolean;
  limit?: number;
}

export interface MemorySearchResponse {
  items: MemoryItem[];
  count: number;
  context: string;
}
