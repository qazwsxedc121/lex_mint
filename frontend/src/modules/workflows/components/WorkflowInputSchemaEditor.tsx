import React from 'react';
import { useTranslation } from 'react-i18next';
import type { WorkflowInputDef } from '../../../types/workflow';

interface WorkflowInputSchemaEditorProps {
  inputs: WorkflowInputDef[];
  nodeIdOptions?: string[];
  disabled?: boolean;
  onChange: (inputs: WorkflowInputDef[]) => void;
}

const createEmptyInputDef = (): WorkflowInputDef => ({
  key: '',
  type: 'string',
  required: false,
  description: '',
});

const normalizeDefaultByType = (
  type: WorkflowInputDef['type'],
  value: WorkflowInputDef['default']
): WorkflowInputDef['default'] => {
  if (type === 'string') {
    if (typeof value === 'string') {
      return value;
    }
    return value === undefined ? undefined : String(value);
  }
  if (type === 'number') {
    return typeof value === 'number' ? value : undefined;
  }
  if (type === 'boolean') {
    return typeof value === 'boolean' ? value : undefined;
  }
  return typeof value === 'string' ? value : undefined;
};

export const WorkflowInputSchemaEditor: React.FC<WorkflowInputSchemaEditorProps> = ({
  inputs,
  nodeIdOptions = [],
  disabled = false,
  onChange,
}) => {
  const { t } = useTranslation('workflow');

  const updateInput = (
    index: number,
    patch: Partial<WorkflowInputDef>,
    forceType?: WorkflowInputDef['type']
  ) => {
    const next = [...inputs];
    const current = next[index];
    if (!current) {
      return;
    }
    const merged = { ...current, ...patch };
    const targetType = forceType ?? merged.type;
    merged.default = normalizeDefaultByType(targetType, merged.default);
    next[index] = merged;
    onChange(next);
  };

  const removeInput = (index: number) => {
    const next = inputs.filter((_, candidateIndex) => candidateIndex !== index);
    onChange(next);
  };

  return (
    <section
      data-name="workflow-input-schema-editor"
      className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-3"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('inputEditor.title')}</h3>
        <button
          type="button"
          data-name="workflow-input-schema-add"
          onClick={() => onChange([...inputs, createEmptyInputDef()])}
          disabled={disabled}
          className="rounded-md px-2 py-1 text-xs font-medium bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-60"
        >
          {t('inputEditor.add')}
        </button>
      </div>

      {inputs.length === 0 ? (
        <div className="rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 px-3 py-4 text-xs text-gray-600 dark:text-gray-300">
          {t('inputEditor.empty')}
        </div>
      ) : (
        <div className="space-y-3">
          {inputs.map((inputDef, index) => {
            const nodeDefaultOptions =
              inputDef.type === 'node' &&
              typeof inputDef.default === 'string' &&
              inputDef.default &&
              !nodeIdOptions.includes(inputDef.default)
                ? [...nodeIdOptions, inputDef.default]
                : nodeIdOptions;

            return (
              <div
              key={`workflow-input-schema-row-${index}`}
              data-name={`workflow-input-schema-row-${index}`}
              className="rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/30 p-3 space-y-2"
            >
              <div className="grid grid-cols-1 lg:grid-cols-6 gap-2">
                <label className="lg:col-span-2 space-y-1">
                  <span className="text-xs text-gray-600 dark:text-gray-300">{t('inputEditor.key')}</span>
                  <input
                    data-name={`workflow-input-schema-key-${index}`}
                    value={inputDef.key}
                    disabled={disabled}
                    onChange={(event) => updateInput(index, { key: event.target.value })}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
                  />
                </label>

                <label className="space-y-1">
                  <span className="text-xs text-gray-600 dark:text-gray-300">{t('inputEditor.type')}</span>
                  <select
                    data-name={`workflow-input-schema-type-${index}`}
                    value={inputDef.type}
                    disabled={disabled}
                    onChange={(event) => {
                      const nextType = event.target.value as WorkflowInputDef['type'];
                      updateInput(index, { type: nextType }, nextType);
                    }}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
                  >
                    <option value="string">string</option>
                    <option value="number">number</option>
                    <option value="boolean">boolean</option>
                    <option value="node">node</option>
                  </select>
                </label>

                <label className="space-y-1">
                  <span className="text-xs text-gray-600 dark:text-gray-300">{t('inputEditor.required')}</span>
                  <button
                    type="button"
                    data-name={`workflow-input-schema-required-${index}`}
                    disabled={disabled}
                    onClick={() => updateInput(index, { required: !inputDef.required })}
                    className={`w-full rounded-md border px-2 py-1.5 text-xs font-medium ${
                      inputDef.required
                        ? 'border-red-300 bg-red-50 text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300'
                        : 'border-gray-300 bg-white text-gray-700 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300'
                    } disabled:opacity-60`}
                  >
                    {inputDef.required ? t('inputEditor.requiredOn') : t('inputEditor.requiredOff')}
                  </button>
                </label>

                <label className="lg:col-span-2 space-y-1">
                  <span className="text-xs text-gray-600 dark:text-gray-300">{t('inputEditor.default')}</span>
                  {inputDef.type === 'boolean' ? (
                    <select
                      data-name={`workflow-input-schema-default-${index}`}
                      value={
                        inputDef.default === true
                          ? 'true'
                          : inputDef.default === false
                            ? 'false'
                            : ''
                      }
                      disabled={disabled}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (!value) {
                          updateInput(index, { default: undefined });
                          return;
                        }
                        updateInput(index, { default: value === 'true' });
                      }}
                      className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
                    >
                      <option value="">{t('inputEditor.defaultUnset')}</option>
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  ) : inputDef.type === 'node' ? (
                    <select
                      data-name={`workflow-input-schema-default-${index}`}
                      value={typeof inputDef.default === 'string' ? inputDef.default : ''}
                      disabled={disabled}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (!value) {
                          updateInput(index, { default: undefined });
                          return;
                        }
                        updateInput(index, { default: value });
                      }}
                      className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
                    >
                      <option value="">{t('inputEditor.defaultUnset')}</option>
                      {nodeDefaultOptions.map((nodeId) => (
                        <option key={`workflow-input-default-node-${index}-${nodeId}`} value={nodeId}>
                          {nodeId}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      data-name={`workflow-input-schema-default-${index}`}
                      type={inputDef.type === 'number' ? 'number' : 'text'}
                      value={inputDef.default === undefined ? '' : String(inputDef.default)}
                      disabled={disabled}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (!value.trim()) {
                          updateInput(index, { default: undefined });
                          return;
                        }
                        if (inputDef.type === 'number') {
                          updateInput(index, { default: Number(value) });
                          return;
                        }
                        updateInput(index, { default: value });
                      }}
                      className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
                    />
                  )}
                </label>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-2 items-end">
                <label className="space-y-1">
                  <span className="text-xs text-gray-600 dark:text-gray-300">{t('inputEditor.description')}</span>
                  <input
                    data-name={`workflow-input-schema-description-${index}`}
                    value={inputDef.description || ''}
                    disabled={disabled}
                    onChange={(event) => updateInput(index, { description: event.target.value })}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-2 py-1.5 text-xs text-gray-900 dark:text-gray-100"
                  />
                </label>
                <button
                  type="button"
                  data-name={`workflow-input-schema-remove-${index}`}
                  disabled={disabled}
                  onClick={() => removeInput(index)}
                  className="rounded-md px-2 py-1.5 text-xs font-medium text-red-600 hover:text-red-500 dark:text-red-400 dark:hover:text-red-300 disabled:opacity-60"
                >
                  {t('inputEditor.remove')}
                </button>
              </div>
            </div>
            );
          })}
        </div>
      )}
    </section>
  );
};
