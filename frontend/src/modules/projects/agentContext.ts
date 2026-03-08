import type { ProjectTextSearchMatch } from '../../services/api';
import type { ProjectAgentContextItem } from './workspace';

const AGENT_CONTEXT_MAX_CHARS = 6000;

const createAgentContextId = (): string => {
  return `agent_ctx_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
};

const truncateContent = (content: string, maxChars: number = AGENT_CONTEXT_MAX_CHARS): { content: string; truncated: boolean } => {
  if (content.length <= maxChars) {
    return { content, truncated: false };
  }

  return {
    content: `${content.slice(0, maxChars)}\n\n[Truncated for Agent context. The Agent can read the full file from the project if needed.]`,
    truncated: true,
  };
};

interface FileAgentContextInput {
  filePath: string;
  text: string;
  startLine: number;
  endLine: number;
  language?: string;
  isSelection: boolean;
}

export const buildFileAgentContextItem = (input: FileAgentContextInput): ProjectAgentContextItem => {
  const normalized = truncateContent(input.text);
  const titlePrefix = input.isSelection ? 'Selected context' : 'File context';

  return {
    id: createAgentContextId(),
    title: `${titlePrefix}: ${input.filePath} lines ${input.startLine}-${input.endLine}`,
    content: normalized.content,
    kind: 'context',
    language: input.language,
    source: {
      filePath: input.filePath,
      startLine: input.startLine,
      endLine: input.endLine,
    },
    origin: 'file',
    createdAt: Date.now(),
  };
};

export const buildSearchAgentContextItem = (
  item: ProjectTextSearchMatch,
  query: string
): ProjectAgentContextItem => {
  return {
    id: createAgentContextId(),
    title: `Search hit: ${item.file_path}:${item.line_number}`,
    content: `Query: ${query}\nFile: ${item.file_path}\nLine: ${item.line_number}\n\n${item.line_text}`,
    kind: 'context',
    language: 'text',
    source: {
      filePath: item.file_path,
      startLine: item.line_number,
      endLine: item.line_number,
    },
    origin: 'search',
    createdAt: Date.now(),
  };
};

export const buildWorkflowAgentContextItem = (input: {
  workflowId: string;
  workflowName: string;
  output: string;
}): ProjectAgentContextItem => {
  const normalized = truncateContent(input.output, 12000);

  return {
    id: createAgentContextId(),
    title: `Workflow output: ${input.workflowName}`,
    content: `Workflow: ${input.workflowName}\nWorkflow ID: ${input.workflowId}\n\n${normalized.content}`,
    kind: 'context',
    language: 'text',
    origin: 'workflow',
    createdAt: Date.now(),
  };
};

export const getAgentContextOriginLabel = (origin: ProjectAgentContextItem['origin']): string => {
  switch (origin) {
    case 'file':
      return 'File';
    case 'search':
      return 'Search';
    case 'workflow':
      return 'Workflow';
    default:
      return 'Context';
  }
};

