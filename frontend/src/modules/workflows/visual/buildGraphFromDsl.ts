import { buildWorkflowLayout } from './layout';
import type {
  VisualGraphBuildResult,
  VisualGraphEdge,
  VisualGraphIssue,
  VisualGraphNode,
  VisualNodeKind,
  VisualNodeStatus,
} from './types';

interface ParsedNode {
  id: string;
  kind: VisualNodeKind;
  order: number;
  raw: Record<string, unknown>;
}

interface ParsedNodeTarget {
  targetId: string;
  label?: string;
}

const NODE_KINDS = new Set<VisualNodeKind>(['start', 'llm', 'condition', 'artifact', 'end']);
const MAX_SUBTITLE_LENGTH = 88;

const emptyResult = (): VisualGraphBuildResult => ({
  nodes: [],
  edges: [],
  issues: [],
  parseError: null,
});

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
};

const asNonEmptyString = (value: unknown): string | null => {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

const truncate = (value: string, maxLength: number): string => {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 3)}...`;
};

const getNodeTitle = (kind: VisualNodeKind): string => {
  if (kind === 'llm') {
    return 'LLM';
  }
  return kind.toUpperCase();
};

const getNodeSubtitle = (node: ParsedNode): string => {
  if (node.kind === 'start') {
    return 'Entry gateway';
  }
  if (node.kind === 'llm') {
    const promptTemplate = asNonEmptyString(node.raw.prompt_template);
    const outputKey = asNonEmptyString(node.raw.output_key);
    if (outputKey) {
      return `output: ${outputKey}`;
    }
    if (promptTemplate) {
      return truncate(promptTemplate, MAX_SUBTITLE_LENGTH);
    }
    return 'LLM execution step';
  }
  if (node.kind === 'condition') {
    const expression = asNonEmptyString(node.raw.expression);
    return expression ? truncate(expression, MAX_SUBTITLE_LENGTH) : 'Branch by expression';
  }
  if (node.kind === 'artifact') {
    const targetPath = asNonEmptyString(node.raw.file_path_template);
    return targetPath ? truncate(targetPath, MAX_SUBTITLE_LENGTH) : 'Write artifact file';
  }
  const resultTemplate = asNonEmptyString(node.raw.result_template);
  return resultTemplate ? truncate(resultTemplate, MAX_SUBTITLE_LENGTH) : 'Finalize output';
};

const collectNodeTargets = (node: ParsedNode): ParsedNodeTarget[] => {
  if (node.kind === 'end') {
    return [];
  }

  if (node.kind === 'condition') {
    const trueNext = asNonEmptyString(node.raw.true_next_id);
    const falseNext = asNonEmptyString(node.raw.false_next_id);
    return [
      ...(trueNext ? [{ targetId: trueNext, label: 'true' }] : []),
      ...(falseNext ? [{ targetId: falseNext, label: 'false' }] : []),
    ];
  }

  const nextId = asNonEmptyString(node.raw.next_id);
  return nextId ? [{ targetId: nextId }] : [];
};

const addMissingTargetIssue = (
  issues: VisualGraphIssue[],
  sourceId: string,
  targetId: string,
  label?: string
) => {
  const exists = issues.some(
    (issue) =>
      issue.code === 'missingTargetNode' &&
      issue.sourceId === sourceId &&
      issue.targetId === targetId &&
      issue.label === label
  );
  if (exists) {
    return;
  }
  issues.push({
    level: 'error',
    code: 'missingTargetNode',
    sourceId,
    targetId,
    label,
  });
};

export const buildGraphFromDsl = (dslText: string): VisualGraphBuildResult => {
  const result = emptyResult();
  let parsedRoot: unknown;

  try {
    parsedRoot = JSON.parse(dslText);
  } catch (error) {
    result.parseError = {
      code: 'invalidJson',
      detail: error instanceof Error ? error.message : undefined,
    };
    return result;
  }

  if (!isRecord(parsedRoot)) {
    result.parseError = {
      code: 'invalidRoot',
    };
    return result;
  }

  const entryNodeId = asNonEmptyString(parsedRoot.entry_node_id);
  if (!entryNodeId) {
    result.parseError = {
      code: 'missingEntryNodeId',
    };
    return result;
  }

  if (!Array.isArray(parsedRoot.nodes)) {
    result.parseError = {
      code: 'missingNodes',
    };
    return result;
  }

  const parsedNodes: ParsedNode[] = [];
  const seenNodeIds = new Set<string>();

  parsedRoot.nodes.forEach((rawNode, index) => {
    if (!isRecord(rawNode)) {
      result.issues.push({
        level: 'error',
        code: 'invalidNodeShape',
        index,
      });
      return;
    }

    const id = asNonEmptyString(rawNode.id);
    const kindCandidate = asNonEmptyString(rawNode.type);

    if (!id || !kindCandidate) {
      result.issues.push({
        level: 'error',
        code: 'invalidNodeShape',
        index,
      });
      return;
    }

    if (!NODE_KINDS.has(kindCandidate as VisualNodeKind)) {
      result.issues.push({
        level: 'error',
        code: 'unknownNodeType',
        nodeId: id,
        nodeType: kindCandidate,
      });
      return;
    }

    if (seenNodeIds.has(id)) {
      result.issues.push({
        level: 'error',
        code: 'duplicateNodeId',
        nodeId: id,
      });
      return;
    }

    seenNodeIds.add(id);
    parsedNodes.push({
      id,
      kind: kindCandidate as VisualNodeKind,
      raw: rawNode,
      order: index,
    });
  });

  if (parsedNodes.length === 0) {
    result.parseError = {
      code: 'noValidNodes',
    };
    return result;
  }

  const nodeById = new Map(parsedNodes.map((node) => [node.id, node]));
  if (!nodeById.has(entryNodeId)) {
    result.issues.push({
      level: 'error',
      code: 'missingEntryNode',
      targetId: entryNodeId,
    });
  }

  const adjacency = new Map<string, string[]>();
  const edges: VisualGraphEdge[] = [];

  parsedNodes.forEach((node) => {
    const targets = collectNodeTargets(node);
    targets.forEach((target, index) => {
      if (!nodeById.has(target.targetId)) {
        addMissingTargetIssue(result.issues, node.id, target.targetId, target.label);
        return;
      }

      const edgeId = `edge-${node.id}-${target.targetId}-${target.label || 'next'}-${index}`;
      edges.push({
        id: edgeId,
        source: node.id,
        target: target.targetId,
        label: target.label,
      });

      const currentTargets = adjacency.get(node.id) ?? [];
      currentTargets.push(target.targetId);
      adjacency.set(node.id, currentTargets);
    });
  });

  const hasEntryNode = nodeById.has(entryNodeId);
  const { positions, reachableNodeIds } = buildWorkflowLayout({
    nodeIdsInOrder: parsedNodes.map((node) => node.id),
    adjacency,
    entryNodeId: hasEntryNode ? entryNodeId : null,
  });

  const nodes: VisualGraphNode[] = parsedNodes.map((node) => {
    const isEntry = node.id === entryNodeId;
    const isOrphan = hasEntryNode && !reachableNodeIds.has(node.id);
    const status: VisualNodeStatus = isEntry ? 'entry' : isOrphan ? 'orphan' : 'normal';

    if (isOrphan) {
      result.issues.push({
        level: 'warn',
        code: 'orphanNode',
        nodeId: node.id,
      });
    }

    return {
      id: node.id,
      position: positions.get(node.id) ?? { x: 0, y: 0 },
      data: {
        nodeId: node.id,
        type: node.kind,
        title: getNodeTitle(node.kind),
        subtitle: getNodeSubtitle(node),
        status,
      },
    };
  });

  result.nodes = nodes;
  result.edges = edges;
  return result;
};
