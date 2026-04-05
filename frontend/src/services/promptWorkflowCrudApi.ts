import { api } from './apiClient';

import type { PromptTemplate, PromptTemplateCreate, PromptTemplateUpdate } from '../types/promptTemplate';
import type { Workflow, WorkflowCreate, WorkflowRunRecord, WorkflowUpdate } from '../types/workflow';

/**
 * Prompt templates CRUD.
 */
export async function listPromptTemplates(): Promise<PromptTemplate[]> {
  const response = await api.get<PromptTemplate[]>('/api/prompt-templates');
  return response.data;
}

export async function getPromptTemplate(templateId: string): Promise<PromptTemplate> {
  const response = await api.get<PromptTemplate>(`/api/prompt-templates/${templateId}`);
  return response.data;
}

export async function createPromptTemplate(template: PromptTemplateCreate): Promise<void> {
  await api.post('/api/prompt-templates', template);
}

export async function updatePromptTemplate(templateId: string, template: PromptTemplateUpdate): Promise<void> {
  await api.put(`/api/prompt-templates/${templateId}`, template);
}

export async function deletePromptTemplate(templateId: string): Promise<void> {
  await api.delete(`/api/prompt-templates/${templateId}`);
}

/**
 * Workflows CRUD.
 */
export async function listWorkflows(): Promise<Workflow[]> {
  const response = await api.get<Workflow[]>('/api/workflows');
  return response.data;
}

export async function getWorkflow(workflowId: string): Promise<Workflow> {
  const response = await api.get<Workflow>(`/api/workflows/${workflowId}`);
  return response.data;
}

export async function createWorkflow(workflow: WorkflowCreate): Promise<string> {
  const response = await api.post<{ id: string }>('/api/workflows', workflow);
  return response.data.id;
}

export async function updateWorkflow(workflowId: string, workflow: WorkflowUpdate): Promise<void> {
  await api.put(`/api/workflows/${workflowId}`, workflow);
}

export async function deleteWorkflow(workflowId: string): Promise<void> {
  await api.delete(`/api/workflows/${workflowId}`);
}

export async function listWorkflowRuns(workflowId: string, limit: number = 50): Promise<WorkflowRunRecord[]> {
  const response = await api.get<WorkflowRunRecord[]>(`/api/workflows/${workflowId}/runs`, {
    params: { limit },
  });
  return response.data;
}

export async function getWorkflowRun(workflowId: string, runId: string): Promise<WorkflowRunRecord> {
  const response = await api.get<WorkflowRunRecord>(`/api/workflows/${workflowId}/runs/${runId}`);
  return response.data;
}
