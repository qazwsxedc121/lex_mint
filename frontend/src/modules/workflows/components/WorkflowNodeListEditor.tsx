import React from 'react';
import { useTranslation } from 'react-i18next';
import type {
  ArtifactNode,
  ConditionNode,
  EndNode,
  LlmNode,
  StartNode,
  WorkflowNode,
  WorkflowNodeType,
} from '../../../types/workflow';

interface WorkflowNodeListEditorProps {
  nodes: WorkflowNode[];
  disabled?: boolean;
  onChange: (nodes: WorkflowNode[]) => void;
  onNodeIdRename?: (fromNodeId: string, toNodeId: string) => void;
}

const createDefaultNode = (type: WorkflowNodeType, seed: number): WorkflowNode => {
  const defaultId = `${type}_${seed}`;
  if (type === 'start') {
    return {
      id: defaultId,
      type: 'start',
      next_id: '',
    };
  }
  if (type === 'llm') {
    return {
      id: defaultId,
      type: 'llm',
      prompt_template: '',
      model_id: '',
      system_prompt: '',
      temperature: null,
      max_tokens: null,
      output_key: '',
      next_id: '',
    };
  }
  if (type === 'condition') {
    return {
      id: defaultId,
      type: 'condition',
      expression: '',
      true_next_id: '',
      false_next_id: '',
    };
  }
  if (type === 'artifact') {
    return {
      id: defaultId,
      type: 'artifact',
      file_path_template: '',
      content_template: '{{ctx.last_output}}',
      write_mode: 'overwrite',
      output_key: '',
      next_id: '',
    };
  }
  return {
    id: defaultId,
    type: 'end',
    result_template: '',
  };
};

const toOptionalString = (value: string): string | null => {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

const toOptionalNumber = (value: string): number | null => {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
};

const collectNodeIds = (nodes: WorkflowNode[]): string[] => {
  const ids: string[] = [];
  const seen = new Set<string>();
  nodes.forEach((node) => {
    const nodeId = node.id.trim();
    if (!nodeId || seen.has(nodeId)) {
      return;
    }
    seen.add(nodeId);
    ids.push(nodeId);
  });
  return ids;
};

const withCurrentNodeIdOption = (options: string[], value: string): string[] => {
  if (!value || options.includes(value)) {
    return options;
  }
  return [...options, value];
};

const remapNodeReferences = (
  nodes: WorkflowNode[],
  fromNodeId: string,
  toNodeId: string
): WorkflowNode[] => {
  const swap = (value: string): string => (value === fromNodeId ? toNodeId : value);
  return nodes.map((node) => {
    if (node.type === 'start') {
      return { ...node, next_id: swap(node.next_id) };
    }
    if (node.type === 'llm') {
      return { ...node, next_id: swap(node.next_id) };
    }
    if (node.type === 'condition') {
      return {
        ...node,
        true_next_id: swap(node.true_next_id),
        false_next_id: swap(node.false_next_id),
      };
    }
    if (node.type === 'artifact') {
      return { ...node, next_id: swap(node.next_id) };
    }
    return node;
  });
};

const NodeIdSelect: React.FC<{
  label: string;
  dataName: string;
  value: string;
  disabled: boolean;
  options: string[];
  placeholder: string;
  className?: string;
  onChange: (value: string) => void;
}> = ({ label, dataName, value, disabled, options, placeholder, className, onChange }) => {
  const resolvedOptions = React.useMemo(
    () => withCurrentNodeIdOption(options, value),
    [options, value]
  );

  return (
    <label className={className || 'space-y-1'}>
      <span className="text-xs text-gray-600 dark:text-gray-300">{label}</span>
      <select
        data-name={dataName}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
      >
        <option value="">{placeholder}</option>
        {resolvedOptions.map((option) => (
          <option key={`${dataName}-${option}`} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
};

const NodeTypeFields: React.FC<{
  node: WorkflowNode;
  index: number;
  disabled: boolean;
  nodeIdOptions: string[];
  updateNode: (patch: Partial<WorkflowNode>) => void;
}> = ({ node, index, disabled, nodeIdOptions, updateNode }) => {
  const { t } = useTranslation('workflow');
  const selectPlaceholder = t('nodeEditor.selectNodePlaceholder');

  if (node.type === 'start') {
    return (
      <NodeIdSelect
        label={t('nodeEditor.nextNode')}
        dataName={`workflow-node-next-${index}`}
        value={(node as StartNode).next_id}
        disabled={disabled}
        options={nodeIdOptions}
        placeholder={selectPlaceholder}
        onChange={(value) => updateNode({ next_id: value })}
      />
    );
  }

  if (node.type === 'llm') {
    const llmNode = node as LlmNode;
    return (
      <div className="space-y-2">
        <label className="space-y-1 block">
          <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.promptTemplate')}</span>
          <textarea
            data-name={`workflow-node-prompt-template-${index}`}
            value={llmNode.prompt_template}
            disabled={disabled}
            onChange={(event) => updateNode({ prompt_template: event.target.value })}
            rows={3}
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
          />
        </label>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
          <label className="space-y-1">
            <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.modelId')}</span>
            <input
              data-name={`workflow-node-model-id-${index}`}
              value={llmNode.model_id || ''}
              disabled={disabled}
              onChange={(event) => updateNode({ model_id: toOptionalString(event.target.value) })}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.outputKey')}</span>
            <input
              data-name={`workflow-node-output-key-${index}`}
              value={llmNode.output_key || ''}
              disabled={disabled}
              onChange={(event) => updateNode({ output_key: toOptionalString(event.target.value) })}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.temperature')}</span>
            <input
              data-name={`workflow-node-temperature-${index}`}
              type="number"
              step="0.1"
              value={llmNode.temperature ?? ''}
              disabled={disabled}
              onChange={(event) => updateNode({ temperature: toOptionalNumber(event.target.value) })}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.maxTokens')}</span>
            <input
              data-name={`workflow-node-max-tokens-${index}`}
              type="number"
              value={llmNode.max_tokens ?? ''}
              disabled={disabled}
              onChange={(event) => updateNode({ max_tokens: toOptionalNumber(event.target.value) })}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
            />
          </label>
          <NodeIdSelect
            className="space-y-1 lg:col-span-2"
            label={t('nodeEditor.nextNode')}
            dataName={`workflow-node-next-${index}`}
            value={llmNode.next_id}
            disabled={disabled}
            options={nodeIdOptions}
            placeholder={selectPlaceholder}
            onChange={(value) => updateNode({ next_id: value })}
          />
        </div>
        <label className="space-y-1 block">
          <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.systemPrompt')}</span>
          <textarea
            data-name={`workflow-node-system-prompt-${index}`}
            value={llmNode.system_prompt || ''}
            disabled={disabled}
            onChange={(event) => updateNode({ system_prompt: toOptionalString(event.target.value) })}
            rows={2}
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
          />
        </label>
      </div>
    );
  }

  if (node.type === 'condition') {
    const conditionNode = node as ConditionNode;
    return (
      <div className="space-y-2">
        <label className="space-y-1 block">
          <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.expression')}</span>
          <input
            data-name={`workflow-node-expression-${index}`}
            value={conditionNode.expression}
            disabled={disabled}
            onChange={(event) => updateNode({ expression: event.target.value })}
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
          />
        </label>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
          <NodeIdSelect
            label={t('nodeEditor.trueNextNode')}
            dataName={`workflow-node-true-next-${index}`}
            value={conditionNode.true_next_id}
            disabled={disabled}
            options={nodeIdOptions}
            placeholder={selectPlaceholder}
            onChange={(value) => updateNode({ true_next_id: value })}
          />
          <NodeIdSelect
            label={t('nodeEditor.falseNextNode')}
            dataName={`workflow-node-false-next-${index}`}
            value={conditionNode.false_next_id}
            disabled={disabled}
            options={nodeIdOptions}
            placeholder={selectPlaceholder}
            onChange={(value) => updateNode({ false_next_id: value })}
          />
        </div>
      </div>
    );
  }

  if (node.type === 'artifact') {
    const artifactNode = node as ArtifactNode;
    return (
      <div className="space-y-2">
        <label className="space-y-1 block">
          <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.filePathTemplate')}</span>
          <input
            data-name={`workflow-node-file-path-template-${index}`}
            value={artifactNode.file_path_template}
            disabled={disabled}
            onChange={(event) => updateNode({ file_path_template: event.target.value })}
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
          />
        </label>
        <label className="space-y-1 block">
          <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.contentTemplate')}</span>
          <textarea
            data-name={`workflow-node-content-template-${index}`}
            value={artifactNode.content_template || ''}
            disabled={disabled}
            onChange={(event) => updateNode({ content_template: event.target.value })}
            rows={3}
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
          />
        </label>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
          <label className="space-y-1">
            <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.writeMode')}</span>
            <select
              data-name={`workflow-node-write-mode-${index}`}
              value={artifactNode.write_mode || 'overwrite'}
              disabled={disabled}
              onChange={(event) => updateNode({ write_mode: event.target.value as ArtifactNode['write_mode'] })}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
            >
              <option value="overwrite">overwrite</option>
              <option value="create">create</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.outputKey')}</span>
            <input
              data-name={`workflow-node-output-key-${index}`}
              value={artifactNode.output_key || ''}
              disabled={disabled}
              onChange={(event) => updateNode({ output_key: toOptionalString(event.target.value) })}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
            />
          </label>
          <NodeIdSelect
            label={t('nodeEditor.nextNode')}
            dataName={`workflow-node-next-${index}`}
            value={artifactNode.next_id}
            disabled={disabled}
            options={nodeIdOptions}
            placeholder={selectPlaceholder}
            onChange={(value) => updateNode({ next_id: value })}
          />
        </div>
      </div>
    );
  }

  const endNode = node as EndNode;
  return (
    <label className="space-y-1 block">
      <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.resultTemplate')}</span>
      <textarea
        data-name={`workflow-node-result-template-${index}`}
        value={endNode.result_template || ''}
        disabled={disabled}
        onChange={(event) => updateNode({ result_template: toOptionalString(event.target.value) })}
        rows={3}
        className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
      />
    </label>
  );
};

export const WorkflowNodeListEditor: React.FC<WorkflowNodeListEditorProps> = ({
  nodes,
  disabled = false,
  onChange,
  onNodeIdRename,
}) => {
  const { t } = useTranslation('workflow');
  const [createType, setCreateType] = React.useState<WorkflowNodeType>('llm');
  const nodeIdOptions = React.useMemo(() => collectNodeIds(nodes), [nodes]);

  const updateNodeAt = (index: number, nextNode: WorkflowNode) => {
    const next = [...nodes];
    if (!next[index]) {
      return;
    }
    next[index] = nextNode;
    onChange(next);
  };

  const removeNode = (index: number) => {
    onChange(nodes.filter((_, candidateIndex) => candidateIndex !== index));
  };

  const renameNodeIdAt = (index: number, nextNodeId: string) => {
    const currentNode = nodes[index];
    if (!currentNode) {
      return;
    }

    const previousNodeId = currentNode.id;
    const nextNodes = [...nodes];
    nextNodes[index] = { ...currentNode, id: nextNodeId };

    if (previousNodeId && nextNodeId && previousNodeId !== nextNodeId) {
      onChange(remapNodeReferences(nextNodes, previousNodeId, nextNodeId));
      if (onNodeIdRename) {
        onNodeIdRename(previousNodeId, nextNodeId);
      }
      return;
    }

    onChange(nextNodes);
  };

  return (
    <section
      data-name="workflow-node-list-editor"
      className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-3"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('nodeEditor.title')}</h3>
        <div className="flex items-center gap-2">
          <select
            data-name="workflow-node-add-type"
            value={createType}
            disabled={disabled}
            onChange={(event) => setCreateType(event.target.value as WorkflowNodeType)}
            className="rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1 text-xs text-gray-900 dark:text-gray-100 disabled:opacity-60"
          >
            <option value="start">start</option>
            <option value="llm">llm</option>
            <option value="condition">condition</option>
            <option value="artifact">artifact</option>
            <option value="end">end</option>
          </select>
          <button
            type="button"
            data-name="workflow-node-add"
            disabled={disabled}
            onClick={() => onChange([...nodes, createDefaultNode(createType, nodes.length + 1)])}
            className="rounded-md px-2 py-1 text-xs font-medium bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-60"
          >
            {t('nodeEditor.add')}
          </button>
        </div>
      </div>

      {nodes.length === 0 ? (
        <div className="rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 px-3 py-4 text-xs text-gray-600 dark:text-gray-300">
          {t('nodeEditor.empty')}
        </div>
      ) : (
        <div className="space-y-3">
          {nodes.map((node, index) => (
            <div
              key={`workflow-node-row-${index}-${node.id}-${node.type}`}
              data-name={`workflow-node-row-${index}`}
              className="rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/30 p-3 space-y-2"
            >
              <div className="grid grid-cols-1 lg:grid-cols-[1fr_180px_auto] gap-2 items-end">
                <label className="space-y-1">
                  <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.id')}</span>
                  <input
                    data-name={`workflow-node-id-${index}`}
                    value={node.id}
                    disabled={disabled}
                    onChange={(event) => renameNodeIdAt(index, event.target.value)}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
                  />
                </label>

                <label className="space-y-1">
                  <span className="text-xs text-gray-600 dark:text-gray-300">{t('nodeEditor.type')}</span>
                  <select
                    data-name={`workflow-node-type-${index}`}
                    value={node.type}
                    disabled={disabled}
                    onChange={(event) => {
                      const nextType = event.target.value as WorkflowNodeType;
                      const nextNode = createDefaultNode(nextType, index + 1);
                      updateNodeAt(index, { ...nextNode, id: node.id || nextNode.id });
                    }}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
                  >
                    <option value="start">start</option>
                    <option value="llm">llm</option>
                    <option value="condition">condition</option>
                    <option value="artifact">artifact</option>
                    <option value="end">end</option>
                  </select>
                </label>

                <button
                  type="button"
                  data-name={`workflow-node-remove-${index}`}
                  disabled={disabled}
                  onClick={() => removeNode(index)}
                  className="rounded-md px-2 py-1.5 text-xs font-medium text-red-600 hover:text-red-500 dark:text-red-400 dark:hover:text-red-300 disabled:opacity-60"
                >
                  {t('nodeEditor.remove')}
                </button>
              </div>

              <NodeTypeFields
                node={node}
                index={index}
                disabled={disabled}
                nodeIdOptions={nodeIdOptions}
                updateNode={(patch) => updateNodeAt(index, { ...node, ...patch } as WorkflowNode)}
              />
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
