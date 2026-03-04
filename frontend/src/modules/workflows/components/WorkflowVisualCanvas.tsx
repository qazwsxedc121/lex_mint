import React from 'react';
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
} from '@xyflow/react';
import type { Edge, Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { VisualGraphEdge, VisualGraphNode, VisualGraphNodeData } from '../visual/types';

interface WorkflowVisualCanvasProps {
  nodes: VisualGraphNode[];
  edges: VisualGraphEdge[];
}

const nodeTypeClassName = (type: VisualGraphNodeData['type']): string => {
  if (type === 'start') {
    return 'border-green-300 bg-green-50 text-green-900 dark:border-green-700 dark:bg-green-900/20 dark:text-green-100';
  }
  if (type === 'condition') {
    return 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-100';
  }
  if (type === 'artifact') {
    return 'border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-700 dark:bg-sky-900/20 dark:text-sky-100';
  }
  if (type === 'end') {
    return 'border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-700 dark:bg-rose-900/20 dark:text-rose-100';
  }
  return 'border-indigo-300 bg-indigo-50 text-indigo-900 dark:border-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-100';
};

const statusBadgeClassName = (status: VisualGraphNodeData['status']): string => {
  if (status === 'entry') {
    return 'bg-blue-600 text-white';
  }
  if (status === 'orphan') {
    return 'bg-amber-600 text-white';
  }
  return 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200';
};

const mapFlowNodes = (nodes: VisualGraphNode[]): Node[] => {
  return nodes.map((node) => ({
    id: node.id,
    position: node.position,
    targetPosition: Position.Left,
    sourcePosition: Position.Right,
    style: {
      width: 'auto',
      padding: 0,
      border: 'none',
      background: 'transparent',
      boxShadow: 'none',
    },
    draggable: false,
    selectable: true,
    className: '!p-0 !border-none !bg-transparent !shadow-none',
    data: {
      label: (
        <div
          data-name={`workflow-visual-node-${node.id}`}
          className={`min-w-[220px] rounded-lg border px-3 py-2 ${nodeTypeClassName(node.data.type)}`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide">{node.data.title}</span>
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${statusBadgeClassName(node.data.status)}`}>
              {node.data.status}
            </span>
          </div>
          <div className="mt-1 text-xs opacity-85">{node.data.subtitle}</div>
          <div className="mt-1 text-[11px] opacity-70">{node.data.nodeId}</div>
        </div>
      ),
    },
  }));
};

const mapFlowEdges = (edges: VisualGraphEdge[]): Edge[] => {
  return edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: 'smoothstep',
    label: edge.label,
    markerEnd: {
      type: MarkerType.ArrowClosed,
    },
  }));
};

export const WorkflowVisualCanvas: React.FC<WorkflowVisualCanvasProps> = ({ nodes, edges }) => {
  const flowNodes = React.useMemo(() => mapFlowNodes(nodes), [nodes]);
  const flowEdges = React.useMemo(() => mapFlowEdges(edges), [edges]);
  const flowKey = React.useMemo(
    () => `${nodes.map((node) => `${node.id}:${node.position.x}:${node.position.y}`).join('|')}::${edges.map((edge) => edge.id).join('|')}`,
    [edges, nodes]
  );

  return (
    <div data-name="workflow-visual-canvas" className="h-[420px] w-full overflow-hidden rounded-md border border-gray-200 dark:border-gray-700">
      <ReactFlowProvider>
        <ReactFlow
          key={flowKey}
          data-name="workflow-visual-flow"
          nodes={flowNodes}
          edges={flowEdges}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.2}
          maxZoom={1.8}
          elementsSelectable
          nodesDraggable={false}
          nodesConnectable={false}
          nodesFocusable={false}
          edgesFocusable={false}
          zoomOnPinch
          panOnDrag
          panOnScroll
          proOptions={{ hideAttribution: true }}
        >
          <MiniMap />
          <Controls />
          <Background gap={20} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
};
