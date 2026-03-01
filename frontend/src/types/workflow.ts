export type WorkflowNodeType = 'start' | 'llm' | 'condition' | 'end';
export type WorkflowScenario = 'general' | 'editor_rewrite';

export interface WorkflowInputDef {
  key: string;
  type: 'string' | 'number' | 'boolean';
  required?: boolean;
  default?: string | number | boolean;
  description?: string | null;
}

export interface StartNode {
  id: string;
  type: 'start';
  next_id: string;
}

export interface LlmNode {
  id: string;
  type: 'llm';
  prompt_template: string;
  model_id?: string | null;
  system_prompt?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  output_key?: string | null;
  next_id: string;
}

export interface ConditionNode {
  id: string;
  type: 'condition';
  expression: string;
  true_next_id: string;
  false_next_id: string;
}

export interface EndNode {
  id: string;
  type: 'end';
  result_template?: string | null;
}

export type WorkflowNode = StartNode | LlmNode | ConditionNode | EndNode;

export interface Workflow {
  id: string;
  name: string;
  description?: string | null;
  enabled: boolean;
  scenario: WorkflowScenario;
  is_system: boolean;
  template_version?: number | null;
  input_schema: WorkflowInputDef[];
  entry_node_id: string;
  nodes: WorkflowNode[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreate {
  id?: string;
  name: string;
  description?: string | null;
  enabled: boolean;
  scenario?: WorkflowScenario;
  is_system?: boolean;
  template_version?: number | null;
  input_schema: WorkflowInputDef[];
  entry_node_id: string;
  nodes: WorkflowNode[];
}

export interface WorkflowUpdate {
  name?: string;
  description?: string | null;
  enabled?: boolean;
  scenario?: WorkflowScenario;
  input_schema?: WorkflowInputDef[];
  entry_node_id?: string;
  nodes?: WorkflowNode[];
}

export interface WorkflowRunRecord {
  run_id: string;
  workflow_id: string;
  status: 'success' | 'error';
  started_at: string;
  finished_at: string;
  duration_ms: number;
  inputs: Record<string, unknown>;
  output?: string | null;
  node_outputs: Record<string, unknown>;
  error?: string | null;
}

export interface WorkflowRunCallbacks {
  onEvent?: (event: WorkflowFlowEvent) => void;
  onChunk?: (chunk: string, event: WorkflowFlowEvent) => void;
  onComplete?: () => void;
  onError?: (message: string) => void;
}

export interface WorkflowFlowEvent {
  event_id: string;
  seq: number;
  ts: number;
  stream_id: string;
  conversation_id?: string;
  turn_id?: string;
  event_type: string;
  stage: 'transport' | 'content' | 'tool' | 'orchestration' | 'meta';
  payload: Record<string, unknown>;
}
