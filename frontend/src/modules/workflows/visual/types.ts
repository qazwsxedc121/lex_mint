export type VisualNodeKind = 'start' | 'llm' | 'condition' | 'artifact' | 'end';

export type VisualNodeStatus = 'entry' | 'normal' | 'orphan';

export interface VisualGraphNodeData {
  nodeId: string;
  type: VisualNodeKind;
  title: string;
  subtitle: string;
  status: VisualNodeStatus;
}

export interface VisualGraphNode {
  id: string;
  position: {
    x: number;
    y: number;
  };
  data: VisualGraphNodeData;
}

export interface VisualGraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export type VisualGraphIssueCode =
  | 'duplicateNodeId'
  | 'missingTargetNode'
  | 'orphanNode'
  | 'unknownNodeType'
  | 'invalidNodeShape'
  | 'missingEntryNode';

export interface VisualGraphIssue {
  level: 'error' | 'warn';
  code: VisualGraphIssueCode;
  nodeId?: string;
  sourceId?: string;
  targetId?: string;
  nodeType?: string;
  index?: number;
  label?: string;
}

export type VisualGraphParseErrorCode =
  | 'invalidJson'
  | 'invalidRoot'
  | 'missingNodes'
  | 'missingEntryNodeId'
  | 'noValidNodes';

export interface VisualGraphParseError {
  code: VisualGraphParseErrorCode;
  detail?: string;
}

export interface VisualGraphBuildResult {
  nodes: VisualGraphNode[];
  edges: VisualGraphEdge[];
  issues: VisualGraphIssue[];
  parseError: VisualGraphParseError | null;
}
