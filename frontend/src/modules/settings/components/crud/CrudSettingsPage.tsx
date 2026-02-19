/**
 * CrudSettingsPage Component
 *
 * Main CRUD page renderer - brings everything together.
 * This component eliminates 200-400 lines of boilerplate per page.
 */

import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PlusIcon } from '@heroicons/react/24/outline';
import { PageHeader, LoadingSpinner, ErrorMessage, SuccessMessage } from '../common';
import { CrudTable } from './CrudTable';
import { CrudModal } from './CrudModal';
import type { CrudSettingsConfig, CrudHook, ConfigContext } from '../../config/types';

interface CrudSettingsPageProps<T> {
  /** Page configuration */
  config: CrudSettingsConfig<T>;
  /** CRUD operations hook */
  hook: CrudHook<T>;
  /** Additional context for dynamic options */
  context?: ConfigContext;
  /** Get item ID */
  getItemId?: (item: T) => string;
}

export function CrudSettingsPage<T = any>({
  config,
  hook,
  context = {},
  getItemId = (item: any) => item.id
}: CrudSettingsPageProps<T>) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingItem, setEditingItem] = useState<T | null>(null);
  const [formData, setFormData] = useState<any>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [togglingIds, setTogglingIds] = useState<Set<string>>(new Set());
  const navigate = useNavigate();
  const { t } = useTranslation('settings');

  const isEdit = editingItem !== null;
  const fields = isEdit && config.editFields ? config.editFields : config.createFields;

  // Initialize form data with defaults
  const initializeFormData = (item?: T) => {
    const data: any = item ? { ...item } : {};

    // Set default values from field configs
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

  // Handle create button
  const handleCreate = () => {
    if (config.createMode === 'page' && config.createPath) {
      navigate(config.createPath);
      return;
    }
    setEditingItem(null);
    setFormData(initializeFormData());
    setShowCreateModal(true);
    setShowErrors(false);
    setSuccessMessage(null);
  };

  // Handle edit button
  const handleEdit = (item: T) => {
    if (config.editMode === 'page' && config.editPath) {
      navigate(config.editPath(getItemId(item), item));
      return;
    }
    setEditingItem(item);
    setFormData(initializeFormData(item));
    setShowCreateModal(true);
    setShowErrors(false);
    setSuccessMessage(null);
  };

  // Handle delete button
  const handleDelete = async (item: T) => {
    const itemId = getItemId(item);
    const itemName = (item as any).name || itemId;

    if (!confirm(t('crud.confirmDelete', { name: itemName }))) {
      return;
    }

    try {
      await hook.deleteItem(itemId);
      setSuccessMessage(t('crud.deletedSuccess', { item: config.itemName }));
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      // Error is handled by the hook
      console.error('Delete error:', err);
    }
  };

  // Handle set default
  const handleSetDefault = async (item: T) => {
    if (!hook.setDefault) return;

    try {
      await hook.setDefault(getItemId(item));
      setSuccessMessage(t('crud.defaultUpdated', { item: config.itemName }));
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      console.error('Set default error:', err);
    }
  };

  // Handle inline status toggle
  const handleToggleStatus = useCallback(async (item: T) => {
    if (!config.statusKey) return;
    const itemId = getItemId(item);

    setTogglingIds(prev => new Set(prev).add(itemId));
    try {
      const updated = { ...item, [config.statusKey!]: !(item as any)[config.statusKey!] };
      await hook.updateItem(itemId, updated);
    } catch (err) {
      console.error('Toggle status error:', err);
    } finally {
      setTogglingIds(prev => {
        const next = new Set(prev);
        next.delete(itemId);
        return next;
      });
    }
  }, [config.statusKey, getItemId, hook]);

  // Handle form submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setShowErrors(true);

    // Validate form
    if (config.validateForm) {
      const error = config.validateForm(formData, isEdit);
      if (error) {
        alert(error);
        return;
      }
    }

    // Check required fields
    for (const field of fields) {
      if (field.required && !formData[field.name]) {
        alert(t('crud.requiredField', { field: field.label }));
        return;
      }

      // Run custom validation
      if (field.validate) {
        const error = field.validate(formData[field.name]);
        if (error) {
          alert(t('crud.fieldError', { field: field.label, error }));
          return;
        }
      }
    }

    try {
      setIsSubmitting(true);

      if (isEdit) {
        await hook.updateItem(getItemId(editingItem!), formData);
        setSuccessMessage(t('crud.updatedSuccess', { item: config.itemName }));
      } else {
        await hook.createItem(formData);
        setSuccessMessage(t('crud.createdSuccess', { item: config.itemName }));
      }

      setShowCreateModal(false);
      setEditingItem(null);
      setFormData({});
      setShowErrors(false);

      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      // Error is handled by the hook
      console.error('Submit error:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle modal close
  const handleCloseModal = () => {
    if (isSubmitting) return;
    setShowCreateModal(false);
    setEditingItem(null);
    setFormData({});
    setShowErrors(false);
  };

  // Render loading state
  if (hook.loading) {
    return config.loadingState || (
      <LoadingSpinner message={t('crud.loadingItems', { items: config.itemNamePlural || config.itemName + 's' })} />
    );
  }

  return (
    <div className="space-y-4" data-name="crud-settings-page">
      {/* Page Header */}
      <PageHeader
        title={config.title}
        description={config.description}
        actions={
          <>
            {/* Global actions */}
            {config.globalActions?.map((action) => (
              <button
                key={action.id}
                onClick={() => action.onClick(null as any, context)}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md ${
                  action.variant === 'danger'
                    ? 'text-white bg-red-600 hover:bg-red-700'
                    : action.variant === 'secondary'
                    ? 'text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600'
                    : 'text-white bg-blue-600 hover:bg-blue-700'
                }`}
              >
                {action.icon && <action.icon className="h-4 w-4" />}
                {action.label}
              </button>
            ))}

            {/* Create button */}
            {config.enableDefaultActions?.create !== false && (
              <button
                onClick={handleCreate}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
              >
                <PlusIcon className="h-4 w-4" />
                {t('crud.addItem', { item: config.itemName })}
              </button>
            )}
          </>
        }
      />

      {/* Success Message */}
      {successMessage && (
        <SuccessMessage
          message={successMessage}
          onDismiss={() => setSuccessMessage(null)}
        />
      )}

      {/* Error Message */}
      {hook.error && (
        <ErrorMessage
          message={hook.error}
          onRetry={hook.refreshData}
        />
      )}

      {/* Table */}
      {!hook.error && (
        <CrudTable
          config={config}
          items={hook.items}
          defaultItemId={hook.defaultItemId}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onSetDefault={hook.setDefault ? handleSetDefault : undefined}
          onToggleStatus={config.statusKey ? handleToggleStatus : undefined}
          togglingIds={togglingIds}
          context={context}
          getItemId={getItemId}
        />
      )}

      {/* Create/Edit Modal */}
      <CrudModal
        isOpen={showCreateModal}
        onClose={handleCloseModal}
        title={isEdit ? t('crud.editItem', { item: config.itemName }) : t('crud.addItem', { item: config.itemName })}
        fields={fields}
        formData={formData}
        onChange={setFormData}
        onSubmit={handleSubmit}
        context={context}
        isEdit={isEdit}
        isSubmitting={isSubmitting}
        showErrors={showErrors}
      />
    </div>
  );
}
