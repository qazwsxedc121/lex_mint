/**
 * CrudCreatePage Component
 *
 * Full-page creator for a CRUD item.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import { PageHeader, LoadingSpinner, ErrorMessage, SuccessMessage } from '../common';
import { CrudForm } from './CrudForm';
import type { CrudSettingsConfig, CrudHook, ConfigContext } from '../../config/types';

interface CrudCreatePageProps<T> {
  /** Page configuration */
  config: CrudSettingsConfig<T>;
  /** CRUD operations hook */
  hook: CrudHook<T>;
  /** Additional context for dynamic options */
  context?: ConfigContext;
  /** Back navigation path */
  backPath: string;
}

export function CrudCreatePage<T = any>({
  config,
  hook,
  context = {},
  backPath
}: CrudCreatePageProps<T>) {
  const initialFormData = useMemo(() => {
    const data: any = {};
    config.createFields.forEach((field) => {
      if (data[field.name] === undefined && 'defaultValue' in field) {
        const skipDefault = field.type === 'slider' && field.allowEmpty;
        if (!skipDefault) {
          data[field.name] = field.defaultValue;
        }
      }
    });
    return data;
  }, [config.createFields]);
  const [formData, setFormData] = useState<any>(initialFormData);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const navigate = useNavigate();
  const pageMeta = config.createPage;

  const fields = useMemo(() => config.createFields, [config.createFields]);

  useEffect(() => {
    setFormData(initialFormData);
  }, [initialFormData]);

  const handleBack = () => {
    if (isSubmitting) return;
    navigate(backPath);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setShowErrors(true);

    if (config.validateForm) {
      const error = config.validateForm(formData, false);
      if (error) {
        alert(error);
        return;
      }
    }

    for (const field of fields) {
      if (field.required && !formData[field.name]) {
        alert(`Please fill in required field: ${field.label}`);
        return;
      }

      if (field.validate) {
        const error = field.validate(formData[field.name]);
        if (error) {
          alert(`${field.label}: ${error}`);
          return;
        }
      }
    }

    try {
      setIsSubmitting(true);
      await hook.createItem(formData);
      setSuccessMessage(pageMeta?.successMessage || `${config.itemName} created successfully`);
      setFormData(initialFormData);
      setShowErrors(false);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      console.error('Submit error:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (hook.loading) {
    return config.loadingState || (
      <LoadingSpinner message={`Loading ${config.itemName}...`} />
    );
  }

  if (hook.error) {
    return (
      <ErrorMessage
        message={hook.error}
        onRetry={hook.refreshData}
      />
    );
  }

  return (
    <div className="space-y-4" data-name="crud-create-page">
      <PageHeader
        title={pageMeta?.title || `Add ${config.itemName}`}
        description={pageMeta?.description || config.description}
        actions={(
          <button
            type="button"
            onClick={handleBack}
            disabled={isSubmitting}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600 disabled:opacity-50"
          >
            <ArrowLeftIcon className="h-4 w-4" />
            {pageMeta?.backLabel || 'Back'}
          </button>
        )}
      />

      {successMessage && (
        <SuccessMessage
          message={successMessage}
          onDismiss={() => setSuccessMessage(null)}
        />
      )}

      {config.customFormRenderer ? (
        config.customFormRenderer(formData, setFormData, context, false)
      ) : (
        <CrudForm
          fields={fields}
          formData={formData}
          onChange={setFormData}
          onSubmit={handleSubmit}
          onCancel={handleBack}
          cancelLabel={pageMeta?.cancelLabel}
          context={context}
          isEdit={false}
          showErrors={showErrors}
          isSubmitting={isSubmitting}
        />
      )}
    </div>
  );
}
