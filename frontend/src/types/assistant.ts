/**
 * Assistant type definitions
 */

export interface Assistant {
  id: string;
  name: string;
  description?: string;
  model_id: string;  // Composite format: provider_id:model_id
  system_prompt?: string;
  temperature?: number;  // null = use model default
  max_rounds?: number;  // Maximum conversation rounds (-1 = unlimited, null/undefined = unlimited)
  enabled: boolean;
}

export interface AssistantCreate {
  id: string;
  name: string;
  description?: string;
  model_id: string;
  system_prompt?: string;
  temperature?: number;
  max_rounds?: number;  // -1 = unlimited
  enabled?: boolean;
}

export interface AssistantUpdate {
  name?: string;
  description?: string;
  model_id?: string;
  system_prompt?: string;
  temperature?: number;
  max_rounds?: number;  // -1 = unlimited
  enabled?: boolean;
}

export interface AssistantsConfig {
  default: string;
  assistants: Assistant[];
}
