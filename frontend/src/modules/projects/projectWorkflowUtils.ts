import type { TFunction } from 'i18next';
import type { Workflow } from '../../types/workflow';
import type { ProjectWorkflowLaunchContext } from './workspace';

const normalizeKey = (key: string): string => key.replace(/^_+/, '').toLowerCase();
const TEXT_PREFILL_KEYS = new Set(['input', 'text', 'selected_text']);
const FILE_PREFILL_KEYS = new Set(['file_path', 'current_file', 'current_path']);

export const buildProjectWorkflowDefaultInputs = (workflow: Workflow): Record<string, unknown> => {
  const defaults: Record<string, unknown> = {};
  for (const inputDef of workflow.input_schema) {
    if (inputDef.default !== undefined) {
      defaults[inputDef.key] = inputDef.default;
    }
  }
  return defaults;
};

export const applyProjectWorkflowLaunchContext = (
  workflow: Workflow,
  inputs: Record<string, unknown>,
  context: ProjectWorkflowLaunchContext | null,
  projectId: string,
  sessionId?: string | null
): Record<string, unknown> => {
  const nextInputs = { ...inputs };

  for (const inputDef of workflow.input_schema) {
    const normalizedKey = normalizeKey(inputDef.key);
    if (normalizedKey === 'project_id') {
      nextInputs[inputDef.key] = projectId;
      continue;
    }
    if (normalizedKey === 'session_id' && sessionId) {
      nextInputs[inputDef.key] = sessionId;
      continue;
    }
    if (!context) {
      continue;
    }
    if (context.filePath && FILE_PREFILL_KEYS.has(normalizedKey)) {
      nextInputs[inputDef.key] = context.filePath;
      continue;
    }
    if (context.selectedText && TEXT_PREFILL_KEYS.has(normalizedKey)) {
      nextInputs[inputDef.key] = context.selectedText;
      continue;
    }
  }

  return nextInputs;
};

export const getWorkflowNodeIds = (workflow: Workflow | null): string[] => {
  if (!workflow) {
    return [];
  }
  const seen = new Set<string>();
  const ids: string[] = [];
  workflow.nodes.forEach((node) => {
    const nodeId = node.id.trim();
    if (!nodeId || seen.has(nodeId)) {
      return;
    }
    seen.add(nodeId);
    ids.push(nodeId);
  });
  return ids;
};

export const validateProjectWorkflowInputs = (
  workflow: Workflow,
  rawInputs: Record<string, unknown>,
  t: TFunction<'projects'>
): { inputs: Record<string, unknown>; error?: string } => {
  const runInputs: Record<string, unknown> = { ...rawInputs };

  for (const inputDef of workflow.input_schema) {
    let value = runInputs[inputDef.key];
    if (value === undefined && inputDef.default !== undefined) {
      value = inputDef.default;
    }

    if (value === undefined || value === null || (inputDef.type !== 'string' && value === '')) {
      if (inputDef.required) {
        return {
          inputs: runInputs,
          error: t('projectWorkflow.missingRequiredInput', { key: inputDef.key }),
        };
      }
      continue;
    }

    if (inputDef.type === 'string') {
      const stringValue = typeof value === 'string' ? value : String(value);
      if (typeof inputDef.max_length === 'number' && stringValue.length > inputDef.max_length) {
        return {
          inputs: runInputs,
          error: `${inputDef.key} exceeds max length (${inputDef.max_length})`,
        };
      }
      if (typeof inputDef.pattern === 'string' && inputDef.pattern.trim()) {
        let matchesPattern = false;
        try {
          const regex = new RegExp(inputDef.pattern);
          matchesPattern = regex.test(stringValue);
        } catch {
          return {
            inputs: runInputs,
            error: `${inputDef.key} has invalid pattern config`,
          };
        }
        if (!matchesPattern) {
          return {
            inputs: runInputs,
            error: `${inputDef.key} format is invalid`,
          };
        }
      }
      runInputs[inputDef.key] = stringValue;
      continue;
    }

    if (inputDef.type === 'number') {
      if (typeof value !== 'number' || Number.isNaN(value)) {
        return {
          inputs: runInputs,
          error: t('projectWorkflow.invalidNumberInput', { key: inputDef.key }),
        };
      }
      runInputs[inputDef.key] = value;
      continue;
    }

    if (inputDef.type === 'boolean') {
      if (typeof value !== 'boolean') {
        return {
          inputs: runInputs,
          error: t('projectWorkflow.invalidBooleanInput', { key: inputDef.key }),
        };
      }
      runInputs[inputDef.key] = value;
      continue;
    }

    if (inputDef.type === 'node') {
      if (typeof value !== 'string' || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(value)) {
        return {
          inputs: runInputs,
          error: t('projectWorkflow.invalidNodeInput', { key: inputDef.key }),
        };
      }
      const hasTargetNode = workflow.nodes.some((node) => node.id === value);
      if (!hasTargetNode) {
        return {
          inputs: runInputs,
          error: t('projectWorkflow.invalidNodeInput', { key: inputDef.key }),
        };
      }
      runInputs[inputDef.key] = value;
    }
  }

  return { inputs: runInputs };
};
