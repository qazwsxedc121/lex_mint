/**
 * FormField Component
 *
 * Generic form field renderer supporting all field types defined in config.
 */

import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { FieldConfig, ConfigContext } from '../../config/types';
import type {
  PromptTemplateVariable,
  PromptTemplateVariableType,
} from '../../../../types/promptTemplate';
import {
  ASSISTANT_ICONS,
  ASSISTANT_ICON_KEYS,
  getAssistantIcon,
} from '../../../../shared/constants/assistantIcons';

const TEMPLATE_VARIABLE_TYPE_OPTIONS: PromptTemplateVariableType[] = ['text', 'number', 'boolean', 'select'];

interface FormFieldProps {
  /** Field configuration */
  config: FieldConfig;
  /** Current field value */
  value: any;
  /** Value change handler */
  onChange: (value: any) => void;
  /** Form data (for conditional rendering) */
  formData: any;
  /** Context data (for dynamic options) */
  context: ConfigContext;
  /** Show validation errors */
  showErrors?: boolean;
}

export const FormField: React.FC<FormFieldProps> = ({
  config,
  value,
  onChange,
  formData,
  context,
  showErrors = false
}) => {
  const { t } = useTranslation('settings');
  // Check conditional rendering
  if (config.condition && !config.condition(formData, context)) {
    return null;
  }

  // Validate field
  const error = showErrors && config.validate ? config.validate(value) : undefined;

  // Common input classes
  const inputClasses = `w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:text-white ${
    error
      ? 'border-red-500 dark:border-red-500'
      : 'border-gray-300 dark:border-gray-600'
  } ${
    config.disabled
      ? 'disabled:opacity-50 disabled:bg-gray-100 dark:disabled:bg-gray-800'
      : ''
  }`;

  const renderField = () => {
    switch (config.type) {
      case 'text':
      case 'password':
        return (
          <input
            type={config.type}
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={config.placeholder}
            required={config.required}
            disabled={config.disabled}
            minLength={config.minLength}
            maxLength={config.maxLength}
            pattern={config.pattern}
            className={inputClasses}
          />
        );

      case 'number':
        return (
          <input
            type="number"
            value={value ?? ''}
            onChange={(e) => {
              const val = e.target.value;
              onChange(val === '' ? undefined : parseFloat(val));
            }}
            placeholder={config.placeholder}
            required={config.required}
            disabled={config.disabled}
            min={config.min}
            max={config.max}
            step={config.step}
            className={inputClasses}
          />
        );

      case 'select': {
        const options = config.dynamicOptions
          ? config.dynamicOptions(context)
          : config.options || [];

        return (
          <select
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            required={config.required}
            disabled={config.disabled}
            className={inputClasses}
          >
            {(config.allowEmpty !== false) && (
              <option value="">{config.emptyLabel || t('common:select')}</option>
            )}
            {options.map((opt) => (
              <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                {opt.label}
              </option>
            ))}
          </select>
        );
      }

      case 'checkbox':
        return (
          <div className="flex items-center">
            <input
              type="checkbox"
              checked={value !== false}
              onChange={(e) => onChange(e.target.checked)}
              disabled={config.disabled}
              className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              id={`checkbox-${config.name}`}
            />
            <label
              htmlFor={`checkbox-${config.name}`}
              className="ml-2 block text-sm text-gray-700 dark:text-gray-300"
            >
              {config.label}
            </label>
          </div>
        );

      case 'slider':
        {
          const allowEmpty = config.allowEmpty;
          const isDefault = allowEmpty && (value === undefined || value === null);
          const effectiveValue = isDefault
            ? (config.defaultValue ?? config.min)
            : (value ?? config.defaultValue ?? config.min);
          const displayValue = isDefault
            ? (config.emptyLabel || t('common:default'))
            : (config.formatValue ? config.formatValue(effectiveValue) : effectiveValue);

        return (
          <div>
            {allowEmpty && (
              <div className="flex items-center gap-2 mb-2">
                <input
                  type="checkbox"
                  checked={isDefault}
                  onChange={(e) => {
                    if (e.target.checked) {
                      onChange(undefined);
                    } else {
                      onChange(config.defaultValue ?? config.min);
                    }
                  }}
                  disabled={config.disabled}
                  className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  id={`slider-default-${config.name}`}
                />
                <label
                  htmlFor={`slider-default-${config.name}`}
                  className="text-xs text-gray-600 dark:text-gray-300"
                >
                  {t('common:useDefault')}
                </label>
              </div>
            )}
            <div className="flex justify-between items-center mb-2">
              {config.showValue !== false && (
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {displayValue}
                </span>
              )}
            </div>
            <input
              type="range"
              min={config.min}
              max={config.max}
              step={config.step}
              value={effectiveValue}
              onChange={(e) => onChange(parseFloat(e.target.value))}
              disabled={config.disabled || isDefault}
              className="w-full"
            />
            {config.showLabels !== false && (
              <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
                <span>{config.minLabel || config.min}</span>
                <span>{config.maxLabel || config.max}</span>
              </div>
              )}
          </div>
        );
      }

      case 'textarea':
        return (
          <textarea
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={config.placeholder}
            required={config.required}
            disabled={config.disabled}
            rows={config.rows || 3}
            minLength={config.minLength}
            maxLength={config.maxLength}
            className={`${inputClasses} ${config.monospace ? 'font-mono text-sm' : ''}`}
          />
        );

      case 'template-variables':
        return (
          <TemplateVariablesField
            variables={Array.isArray(value) ? value : []}
            disabled={config.disabled}
            onChange={onChange}
          />
        );

      case 'icon-picker': {
        const selectedKey = value || '';
        const SelectedIcon = selectedKey ? getAssistantIcon(selectedKey) : null;
        const columns = config.columns || 10;

        return <IconPickerField
          selectedKey={selectedKey}
          SelectedIcon={SelectedIcon}
          columns={columns}
          onChange={onChange}
        />;
      }

      case 'multi-select': {
        const options = config.dynamicOptions
          ? config.dynamicOptions(context)
          : config.options || [];
        const selectedValues: string[] = Array.isArray(value) ? value : [];

        const toggleValue = (val: string) => {
          if (selectedValues.includes(val)) {
            onChange(selectedValues.filter((v: string) => v !== val));
          } else {
            onChange([...selectedValues, val]);
          }
        };

        return (
          <div className="space-y-1 max-h-48 overflow-y-auto border border-gray-300 dark:border-gray-600 rounded-md p-2 bg-white dark:bg-gray-700">
            {options.length === 0 ? (
              <div className="text-sm text-gray-400 dark:text-gray-500 py-1">{t('common:noOptions')}</div>
            ) : (
              options.map((opt) => (
                <label
                  key={opt.value}
                  className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-50 dark:hover:bg-gray-600 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedValues.includes(opt.value)}
                    onChange={() => toggleValue(opt.value)}
                    disabled={config.disabled || opt.disabled}
                    className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">{opt.label}</span>
                </label>
              ))
            )}
          </div>
        );
      }

      case 'preset':
        return (
          <div className="flex flex-wrap gap-2" data-name={`preset-${config.name}`}>
            {config.options.map((opt) => {
              const isActive = Object.entries(opt.effects).every(
                ([k, v]) => formData[k] === v
              );
              return (
                <button
                  key={opt.value}
                  type="button"
                  disabled={config.disabled}
                  onClick={() => onChange(opt.effects)}
                  className={`px-4 py-2 rounded-lg border text-left transition-colors ${
                    isActive
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 ring-1 ring-blue-500'
                      : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:border-blue-300 dark:hover:border-blue-600 hover:bg-blue-50/50 dark:hover:bg-blue-900/10'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  <div className="text-sm font-medium">{opt.label}</div>
                  {opt.description && (
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{opt.description}</div>
                  )}
                </button>
              );
            })}
          </div>
        );

      default:
        return <div className="text-red-500">{t('formField.unknownType')}</div>;
    }
  };

  // For checkbox, label is rendered inline
  if (config.type === 'checkbox') {
    return (
      <div data-name={`form-field-${config.name}`}>
        {renderField()}
        {config.helpText && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-6">
            {config.helpText}
          </p>
        )}
        {error && (
          <p className="text-xs text-red-600 dark:text-red-400 mt-1 ml-6">
            {error}
          </p>
        )}
      </div>
    );
  }

  // For other fields, label is above
  return (
    <div data-name={`form-field-${config.name}`}>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        {config.label}
        {config.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {renderField()}
      {config.helpText && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          {config.helpText}
        </p>
      )}
      {error && (
        <p className="text-xs text-red-600 dark:text-red-400 mt-1">
          {error}
        </p>
      )}
    </div>
  );
};

const normalizeTemplateVariables = (variables: PromptTemplateVariable[]): PromptTemplateVariable[] =>
  variables.map((variable) => ({
    ...variable,
    key: variable.key ?? '',
    label: variable.label ?? '',
    description: variable.description ?? '',
    type: variable.type ?? 'text',
    required: variable.required === true,
    default: variable.default ?? null,
    options: Array.isArray(variable.options) ? variable.options : [],
  }));

const optionsToText = (options: string[] | undefined): string =>
  Array.isArray(options) ? options.join('\n') : '';

const textToOptions = (input: string): string[] => {
  const items = input
    .split('\n')
    .flatMap((line) => line.split(','))
    .map((item) => item.trim())
    .filter(Boolean);
  return Array.from(new Set(items));
};

const normalizeDefaultForType = (
  type: PromptTemplateVariableType,
  value: PromptTemplateVariable['default'],
): PromptTemplateVariable['default'] => {
  if (value === undefined || value === null) {
    return null;
  }

  if (type === 'text') {
    return typeof value === 'string' ? value : null;
  }
  if (type === 'number') {
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
  }
  if (type === 'boolean') {
    return typeof value === 'boolean' ? value : null;
  }
  return typeof value === 'string' ? value : null;
};

const TemplateVariablesField: React.FC<{
  variables: PromptTemplateVariable[];
  disabled?: boolean;
  onChange: (value: PromptTemplateVariable[]) => void;
}> = ({ variables, disabled, onChange }) => {
  const { t } = useTranslation('settings');
  const normalizedVariables = normalizeTemplateVariables(variables);

  const updateVariable = (
    index: number,
    updater: (variable: PromptTemplateVariable) => PromptTemplateVariable,
  ) => {
    const next = normalizedVariables.map((variable, variableIndex) =>
      variableIndex === index ? updater(variable) : variable,
    );
    onChange(next);
  };

  const removeVariable = (index: number) => {
    onChange(normalizedVariables.filter((_, variableIndex) => variableIndex !== index));
  };

  const addVariable = () => {
    onChange([
      ...normalizedVariables,
      {
        key: '',
        label: '',
        description: '',
        type: 'text',
        required: false,
        default: null,
        options: [],
      },
    ]);
  };

  return (
    <div className="space-y-3" data-name="template-variables-editor">
      {normalizedVariables.length === 0 ? (
        <div className="text-sm text-gray-500 dark:text-gray-400 border border-dashed border-gray-300 dark:border-gray-600 rounded-md px-3 py-4">
          {t('promptTemplates.field.variables.empty')}
        </div>
      ) : (
        normalizedVariables.map((variable, index) => {
          const type = variable.type || 'text';
          const options = Array.isArray(variable.options) ? variable.options : [];
          const defaultValue = normalizeDefaultForType(type, variable.default);

          return (
            <div
              key={`template-variable-${index}`}
              className="rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/60 p-3 space-y-3"
              data-name="template-variables-editor-row"
            >
              <div className="flex items-center justify-between">
                <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  {t('promptTemplates.field.variables.variableLabel', { index: index + 1 })}
                </div>
                <button
                  type="button"
                  onClick={() => removeVariable(index)}
                  disabled={disabled}
                  className="text-xs text-red-600 dark:text-red-400 hover:underline disabled:opacity-50"
                >
                  {t('promptTemplates.field.variables.remove')}
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div data-name="template-variables-editor-key">
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {t('promptTemplates.field.variables.key')}
                  </label>
                  <input
                    type="text"
                    value={variable.key || ''}
                    onChange={(event) =>
                      updateVariable(index, (current) => ({ ...current, key: event.target.value }))
                    }
                    disabled={disabled}
                    placeholder={t('promptTemplates.field.variables.keyPlaceholder')}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white"
                  />
                </div>

                <div data-name="template-variables-editor-label">
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {t('promptTemplates.field.variables.itemLabel')}
                  </label>
                  <input
                    type="text"
                    value={variable.label || ''}
                    onChange={(event) =>
                      updateVariable(index, (current) => ({ ...current, label: event.target.value }))
                    }
                    disabled={disabled}
                    placeholder={t('promptTemplates.field.variables.labelPlaceholder')}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white"
                  />
                </div>
              </div>

              <div data-name="template-variables-editor-description">
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {t('promptTemplates.field.variables.description')}
                </label>
                <input
                  type="text"
                  value={variable.description || ''}
                  onChange={(event) =>
                    updateVariable(index, (current) => ({ ...current, description: event.target.value }))
                  }
                  disabled={disabled}
                  placeholder={t('promptTemplates.field.variables.descriptionPlaceholder')}
                  className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div data-name="template-variables-editor-type">
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {t('promptTemplates.field.variables.type')}
                  </label>
                  <select
                    value={type}
                    onChange={(event) =>
                      updateVariable(index, (current) => {
                        const nextType = event.target.value as PromptTemplateVariableType;
                        const nextDefault = normalizeDefaultForType(nextType, current.default);
                        return {
                          ...current,
                          type: nextType,
                          default: nextDefault,
                          options: nextType === 'select'
                            ? (Array.isArray(current.options) ? current.options : [])
                            : [],
                        };
                      })
                    }
                    disabled={disabled}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white"
                  >
                    {TEMPLATE_VARIABLE_TYPE_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {t(`promptTemplates.field.variables.typeOptions.${option}`)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center pt-6" data-name="template-variables-editor-required">
                  <input
                    type="checkbox"
                    checked={variable.required === true}
                    onChange={(event) =>
                      updateVariable(index, (current) => ({ ...current, required: event.target.checked }))
                    }
                    disabled={disabled}
                    id={`template-variable-required-${index}`}
                    className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <label
                    htmlFor={`template-variable-required-${index}`}
                    className="ml-2 text-sm text-gray-700 dark:text-gray-300"
                  >
                    {t('promptTemplates.field.variables.required')}
                  </label>
                </div>
              </div>

              {type === 'select' && (
                <div data-name="template-variables-editor-options">
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {t('promptTemplates.field.variables.options')}
                  </label>
                  <textarea
                    value={optionsToText(options)}
                    onChange={(event) =>
                      updateVariable(index, (current) => {
                        const nextOptions = textToOptions(event.target.value);
                        const currentDefault = typeof current.default === 'string' ? current.default : null;
                        return {
                          ...current,
                          options: nextOptions,
                          default: currentDefault && nextOptions.includes(currentDefault)
                            ? currentDefault
                            : null,
                        };
                      })
                    }
                    disabled={disabled}
                    rows={3}
                    placeholder={t('promptTemplates.field.variables.optionsPlaceholder')}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white"
                  />
                </div>
              )}

              <div data-name="template-variables-editor-default">
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {t('promptTemplates.field.variables.default')}
                </label>
                {type === 'boolean' ? (
                  <select
                    value={typeof defaultValue === 'boolean' ? (defaultValue ? 'true' : 'false') : ''}
                    onChange={(event) =>
                      updateVariable(index, (current) => ({
                        ...current,
                        default: event.target.value === ''
                          ? null
                          : event.target.value === 'true',
                      }))
                    }
                    disabled={disabled}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white"
                  >
                    <option value="">{t('promptTemplates.field.variables.noDefault')}</option>
                    <option value="true">{t('common:yes')}</option>
                    <option value="false">{t('common:no')}</option>
                  </select>
                ) : type === 'number' ? (
                  <input
                    type="number"
                    value={typeof defaultValue === 'number' ? defaultValue : ''}
                    onChange={(event) =>
                      updateVariable(index, (current) => {
                        const nextRaw = event.target.value;
                        const parsed = Number(nextRaw);
                        return {
                          ...current,
                          default: nextRaw === '' || !Number.isFinite(parsed) ? null : parsed,
                        };
                      })
                    }
                    disabled={disabled}
                    placeholder={t('promptTemplates.field.variables.defaultPlaceholder')}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white"
                  />
                ) : type === 'select' ? (
                  <select
                    value={typeof defaultValue === 'string' ? defaultValue : ''}
                    onChange={(event) =>
                      updateVariable(index, (current) => ({
                        ...current,
                        default: event.target.value || null,
                      }))
                    }
                    disabled={disabled || options.length === 0}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white"
                  >
                    <option value="">{t('promptTemplates.field.variables.noDefault')}</option>
                    {options.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={typeof defaultValue === 'string' ? defaultValue : ''}
                    onChange={(event) =>
                      updateVariable(index, (current) => ({ ...current, default: event.target.value }))
                    }
                    disabled={disabled}
                    placeholder={t('promptTemplates.field.variables.defaultPlaceholder')}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white"
                  />
                )}
              </div>
            </div>
          );
        })
      )}

      <button
        type="button"
        onClick={addVariable}
        disabled={disabled}
        className="inline-flex items-center rounded-md border border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/30 px-3 py-1.5 text-sm font-medium text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/40 disabled:opacity-50"
      >
        {t('promptTemplates.field.variables.add')}
      </button>
    </div>
  );
};

/** Max icons shown per page in the grid to keep rendering fast */
const PAGE_SIZE = 200;

/** Collapsible icon picker with search */
const IconPickerField: React.FC<{
  selectedKey: string;
  SelectedIcon: ReturnType<typeof getAssistantIcon> | null;
  columns: number;
  onChange: (key: string) => void;
}> = ({ selectedKey, SelectedIcon, columns, onChange }) => {
  const { t } = useTranslation('settings');
  const [expanded, setExpanded] = useState(false);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const filteredKeys = useMemo(() => {
    if (!search.trim()) return ASSISTANT_ICON_KEYS;
    const q = search.trim().toLowerCase();
    return ASSISTANT_ICON_KEYS.filter((k) => k.toLowerCase().includes(q));
  }, [search]);

  const visibleKeys = useMemo(
    () => filteredKeys.slice(0, page * PAGE_SIZE),
    [filteredKeys, page],
  );

  const hasMore = visibleKeys.length < filteredKeys.length;

  return (
    <div data-name="icon-picker-field">
      {/* Collapsed state: show selected icon + toggle button */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-3 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
      >
        <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center shrink-0">
          {SelectedIcon ? (
            <SelectedIcon className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          ) : (
            <span className="text-xs text-gray-400 dark:text-gray-500">--</span>
          )}
        </div>
        <span className="text-sm text-gray-700 dark:text-gray-300 flex-1 text-left">
          {selectedKey || t('formField.clickToChooseIcon')}
        </span>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Expanded panel */}
      {expanded && (
        <div className="mt-2 border border-gray-200 dark:border-gray-600 rounded-md overflow-hidden">
          {/* Search input */}
          <div className="p-2 border-b border-gray-200 dark:border-gray-600">
            <input
              type="text"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder={t('formField.searchIcons')}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white placeholder-gray-400"
            />
            <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              {search.trim() ? t('formField.iconsFound', { count: filteredKeys.length }) : t('formField.iconsAvailable', { count: filteredKeys.length })}
            </div>
          </div>

          {/* Icon grid */}
          <div
            className="max-h-64 overflow-y-auto p-2"
            style={{ display: 'grid', gridTemplateColumns: `repeat(${columns}, 1fr)`, gap: '4px' }}
          >
            {visibleKeys.map((key) => {
              const Icon = ASSISTANT_ICONS[key];
              const isSelected = key === selectedKey;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => { onChange(key); setExpanded(false); }}
                  title={key}
                  className={`w-8 h-8 flex items-center justify-center rounded transition-colors ${
                    isSelected
                      ? 'ring-2 ring-blue-500 bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400'
                      : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                </button>
              );
            })}
          </div>

          {/* Load more */}
          {hasMore && (
            <div className="p-2 border-t border-gray-200 dark:border-gray-600 text-center">
              <button
                type="button"
                onClick={() => setPage((p) => p + 1)}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                {t('formField.loadMore', { count: filteredKeys.length - visibleKeys.length })}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
