/**
 * FormField Component
 *
 * Generic form field renderer supporting all field types defined in config.
 */

import React from 'react';
import type { FieldConfig, ConfigContext } from '../../config/types';

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
        return (
          <div>
            <div className="flex justify-between items-center mb-2">
              {config.showValue !== false && (
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {config.formatValue ? config.formatValue(value ?? config.defaultValue ?? config.min) : (value ?? config.defaultValue ?? config.min)}
                </span>
              )}
            </div>
            <input
              type="range"
              min={config.min}
              max={config.max}
              step={config.step}
              value={value ?? config.defaultValue ?? config.min}
              onChange={(e) => onChange(parseFloat(e.target.value))}
              disabled={config.disabled}
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
