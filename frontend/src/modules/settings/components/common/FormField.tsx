/**
 * FormField Component
 *
 * Generic form field renderer supporting all field types defined in config.
 */

import React, { useState, useMemo } from 'react';
import type { FieldConfig, ConfigContext } from '../../config/types';
import {
  ASSISTANT_ICONS,
  ASSISTANT_ICON_KEYS,
  getAssistantIcon,
} from '../../../../shared/constants/assistantIcons';

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
              <option value="">{config.emptyLabel || 'Select...'}</option>
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
            ? (config.emptyLabel || 'Default')
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
                  Use default
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
              <div className="text-sm text-gray-400 dark:text-gray-500 py-1">No options available</div>
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

      default:
        return <div className="text-red-500">Unknown field type</div>;
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

/** Max icons shown per page in the grid to keep rendering fast */
const PAGE_SIZE = 200;

/** Collapsible icon picker with search */
const IconPickerField: React.FC<{
  selectedKey: string;
  SelectedIcon: ReturnType<typeof getAssistantIcon> | null;
  columns: number;
  onChange: (key: string) => void;
}> = ({ selectedKey, SelectedIcon, columns, onChange }) => {
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
          {selectedKey || 'Click to choose an icon'}
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
              placeholder="Search icons..."
              className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white placeholder-gray-400"
            />
            <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              {filteredKeys.length} icons{search.trim() ? ' found' : ' available'}
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
                Load more ({filteredKeys.length - visibleKeys.length} remaining)
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
