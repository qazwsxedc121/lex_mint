/**
 * Prompt template type definitions.
 */

export interface PromptTemplate {
  id: string;
  name: string;
  description?: string;
  content: string;
  enabled?: boolean;
}

export interface PromptTemplateCreate {
  name: string;
  description?: string;
  content: string;
  enabled?: boolean;
}

export interface PromptTemplateUpdate {
  name?: string;
  description?: string;
  content?: string;
  enabled?: boolean;
}
