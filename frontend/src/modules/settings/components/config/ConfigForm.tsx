/**
 * ConfigForm Component
 *
 * Dynamic form for simple configuration pages.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { FormField } from '../common';
import type { FieldConfig, ConfigContext } from '../../config/types';

interface ConfigFormProps {
  /** Form fields configuration */
  fields: FieldConfig[];
  /** Current form data */
  formData: any;
  /** Form data change handler */
  onChange: (data: any) => void;
  /** Context for dynamic options */
  context: ConfigContext;
  /** Show validation errors */
  showErrors?: boolean;
  /** Form submit handler */
  onSubmit: (e: React.FormEvent) => void;
  /** Is submitting */
  isSubmitting?: boolean;
  /** Submit button label */
  submitLabel?: string;
  /** Custom action buttons */
  customActions?: React.ReactNode;
}

export const ConfigForm: React.FC<ConfigFormProps> = ({
  fields,
  formData,
  onChange,
  context,
  showErrors = false,
  onSubmit,
  isSubmitting = false,
  submitLabel,
  customActions
}) => {
  const { t } = useTranslation('settings');
  const resolvedSubmitLabel = submitLabel ?? t('config.saveSettings');
  const handleFieldChange = (fieldName: string, value: any) => {
    onChange({ ...formData, [fieldName]: value });
  };

  return (
    <form onSubmit={onSubmit} className="space-y-6" data-name="config-form">
      {/* Render all form fields */}
      {fields.map((field) => (
        <FormField
          key={field.name}
          config={field}
          value={formData[field.name]}
          onChange={(value) => handleFieldChange(field.name, value)}
          formData={formData}
          context={context}
          showErrors={showErrors}
        />
      ))}

      {/* Action buttons */}
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:cursor-not-allowed"
        >
          {isSubmitting ? t('common:saving') : resolvedSubmitLabel}
        </button>

        {customActions}
      </div>
    </form>
  );
};
