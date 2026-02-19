/**
 * CrudForm Component
 *
 * Dynamic form renderer based on field configuration.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { FormField } from '../common';
import type { FieldConfig, ConfigContext } from '../../config/types';

interface CrudFormProps {
  /** Form fields configuration */
  fields: FieldConfig[];
  /** Current form data */
  formData: any;
  /** Form data change handler */
  onChange: (data: any) => void;
  /** Context for dynamic options */
  context: ConfigContext;
  /** Whether this is edit mode */
  isEdit: boolean;
  /** Show validation errors */
  showErrors?: boolean;
  /** Form submit handler */
  onSubmit: (e: React.FormEvent) => void;
  /** Cancel handler */
  onCancel: () => void;
  /** Submit button label */
  submitLabel?: string;
  /** Cancel button label */
  cancelLabel?: string;
  /** Is submitting */
  isSubmitting?: boolean;
}

export const CrudForm: React.FC<CrudFormProps> = ({
  fields,
  formData,
  onChange,
  context,
  isEdit,
  showErrors = false,
  onSubmit,
  onCancel,
  submitLabel,
  cancelLabel,
  isSubmitting = false
}) => {
  const { t } = useTranslation('common');
  const resolvedCancelLabel = cancelLabel ?? t('cancel');

  const handleFieldChange = (fieldName: string, value: any) => {
    // Support batch field updates (e.g., from model-id field selecting a model)
    if (value && typeof value === 'object' && value.__batchUpdate) {
      const { __batchUpdate, ...fields } = value;
      onChange({ ...formData, ...fields });
    } else {
      onChange({ ...formData, [fieldName]: value });
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4" data-name="crud-form">
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
      <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600 disabled:opacity-50"
        >
          {resolvedCancelLabel}
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? t('saving') : (submitLabel || (isEdit ? t('save') : t('create')))}
        </button>
      </div>
    </form>
  );
};
