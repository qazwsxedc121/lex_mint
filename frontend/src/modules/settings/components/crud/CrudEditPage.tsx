/**
 * CrudEditPage Component
 *
 * Full-page editor for a CRUD item.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import { PageHeader, LoadingSpinner, ErrorMessage, SuccessMessage } from '../common';
import { CrudForm } from './CrudForm';
import type { CrudSettingsConfig, CrudHook, ConfigContext } from '../../config/types';

interface CrudEditPageProps<T> {
  /** Page configuration */
  config: CrudSettingsConfig<T>;
  /** CRUD operations hook */
  hook: CrudHook<T>;
  /** Item ID to edit */
  itemId: string;
  /** Additional context for dynamic options */
  context?: ConfigContext;
  /** Get item ID */
  getItemId?: (item: T) => string;
  /** Back navigation path */
  backPath: string;
}

export function CrudEditPage<T = any>({
  config,
  hook,
  itemId,
  context = {},
  getItemId = (item: any) => item.id,
  backPath
}: CrudEditPageProps<T>) {
  const [formData, setFormData] = useState<any>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const navigate = useNavigate();
  const pageMeta = config.editPage;

  const fields = config.editFields ? config.editFields : config.createFields;

  const item = useMemo(
    () => hook.items.find((entry) => getItemId(entry) === itemId),
    [hook.items, getItemId, itemId]
  );

  const initializeFormData = (source?: T) => {
    const data: any = source ? { ...source } : {};

    fields.forEach((field) => {
      if (data[field.name] === undefined && 'defaultValue' in field) {
        const skipDefault = field.type === 'slider' && field.allowEmpty;
        if (!skipDefault) {
          data[field.name] = field.defaultValue;
        }
      }
    });

    return data;
  };

  useEffect(() => {
    if (item) {
      setFormData(initializeFormData(item));
      setShowErrors(false);
      setSuccessMessage(null);
    }
  }, [item]);

  const handleBack = () => {
    if (isSubmitting) return;
    navigate(backPath);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setShowErrors(true);

    if (config.validateForm) {
      const error = config.validateForm(formData, true);
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
      await hook.updateItem(itemId, formData);
      const successText = pageMeta?.successMessage;
      setSuccessMessage(
        typeof successText === 'function'
          ? successText(item)
          : (successText || `${config.itemName} updated successfully`)
      );
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

  if (!item) {
    return (
      <ErrorMessage
        message={`${config.itemName} not found`}
        onRetry={hook.refreshData}
      />
    );
  }

  return (
    <div className="space-y-4" data-name="crud-edit-page">
      <PageHeader
        title={
          typeof pageMeta?.title === 'function'
            ? pageMeta.title(item)
            : (pageMeta?.title || `Edit ${config.itemName}`)
        }
        description={
          typeof pageMeta?.description === 'function'
            ? pageMeta.description(item)
            : (pageMeta?.description || ((item as any)?.name ? `Editing ${(item as any).name}` : undefined))
        }
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
        config.customFormRenderer(formData, setFormData, context, true)
      ) : (
        <CrudForm
          fields={fields}
          formData={formData}
          onChange={setFormData}
          onSubmit={handleSubmit}
          onCancel={handleBack}
          cancelLabel={pageMeta?.cancelLabel}
          context={context}
          isEdit={true}
          showErrors={showErrors}
          isSubmitting={isSubmitting}
        />
      )}
    </div>
  );
}
