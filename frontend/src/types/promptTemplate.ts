/**
 * Prompt template type definitions.
 */

export type PromptTemplateVariableType = 'text' | 'number' | 'boolean' | 'select';

export interface PromptTemplateVariable {
  key: string;
  label?: string;
  description?: string;
  type?: PromptTemplateVariableType;
  required?: boolean;
  default?: string | number | boolean | null;
  options?: string[];
}

export interface PromptTemplate {
  id: string;
  name: string;
  description?: string;
  trigger?: string;
  aliases?: string[];
  content: string;
  enabled?: boolean;
  variables?: PromptTemplateVariable[];
}

export interface PromptTemplateCreate {
  name: string;
  description?: string;
  trigger?: string;
  aliases?: string[];
  content: string;
  enabled?: boolean;
  variables?: PromptTemplateVariable[];
}

export interface PromptTemplateUpdate {
  name?: string;
  description?: string;
  trigger?: string;
  aliases?: string[];
  content?: string;
  enabled?: boolean;
  variables?: PromptTemplateVariable[];
}
