import { api } from './apiClient';

/**
 * Run a workflow or async chat task and consume the related flow_event stream elsewhere.
 */
export interface WorkflowRunStreamOptions {
  sessionId?: string;
  contextType?: 'workflow' | 'chat' | 'project';
  projectId?: string;
  streamMode?: 'default' | 'editor_rewrite';
  artifactTargetPath?: string;
  writeMode?: 'none' | 'create' | 'overwrite';
}

export type AsyncRunKind = 'workflow' | 'chat';
export type AsyncRunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface AsyncRunRecord {
  run_id: string;
  stream_id: string;
  kind: AsyncRunKind;
  status: AsyncRunStatus;
  context_type: 'workflow' | 'chat' | 'project';
  project_id?: string | null;
  session_id?: string | null;
  workflow_id?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  request_payload: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  error?: string | null;
  last_event_id?: string | null;
  last_seq: number;
}

export interface ListAsyncRunsOptions {
  limit?: number;
  kind?: AsyncRunKind;
  status?: AsyncRunStatus;
  contextType?: 'workflow' | 'chat' | 'project';
  projectId?: string;
  sessionId?: string;
  workflowId?: string;
}

interface AsyncRunListResponse {
  runs: AsyncRunRecord[];
}

export async function createAsyncRun(payload: {
  kind: AsyncRunKind;
  workflow_id?: string;
  inputs?: Record<string, unknown>;
  session_id?: string;
  context_type?: 'workflow' | 'chat' | 'project';
  project_id?: string;
  stream_mode?: 'default' | 'editor_rewrite';
  artifact_target_path?: string;
  write_mode?: 'none' | 'create' | 'overwrite';
}): Promise<AsyncRunRecord> {
  const response = await api.post<AsyncRunRecord>('/api/runs', payload);
  return response.data;
}

export async function createWorkflowRun(
  workflowId: string,
  inputs: Record<string, unknown>,
  options?: WorkflowRunStreamOptions,
): Promise<AsyncRunRecord> {
  return createAsyncRun({
    kind: 'workflow',
    workflow_id: workflowId,
    inputs,
    session_id: options?.sessionId,
    context_type: options?.contextType || 'workflow',
    project_id: options?.projectId,
    stream_mode: options?.streamMode || 'default',
    artifact_target_path: options?.artifactTargetPath,
    write_mode: options?.writeMode,
  });
}

export async function listAsyncRuns(options?: ListAsyncRunsOptions): Promise<AsyncRunRecord[]> {
  const response = await api.get<AsyncRunListResponse>('/api/runs', {
    params: {
      limit: options?.limit ?? 50,
      kind: options?.kind,
      status: options?.status,
      context_type: options?.contextType,
      project_id: options?.projectId,
      session_id: options?.sessionId,
      workflow_id: options?.workflowId,
    },
  });
  return response.data.runs;
}

export async function getAsyncRun(runId: string): Promise<AsyncRunRecord> {
  const response = await api.get<AsyncRunRecord>(`/api/runs/${runId}`);
  return response.data;
}

export async function cancelAsyncRun(runId: string): Promise<AsyncRunRecord> {
  const response = await api.post<AsyncRunRecord>(`/api/runs/${runId}/cancel`);
  return response.data;
}
