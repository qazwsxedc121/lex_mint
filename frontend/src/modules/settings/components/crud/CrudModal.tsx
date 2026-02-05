/**
 * CrudModal Component
 *
 * Modal for creating or editing CRUD items.
 */

import React from 'react';
import { Modal } from '../common';
import { CrudForm } from './CrudForm';
import type { FieldConfig, ConfigContext } from '../../config/types';

interface CrudModalProps {
  /** Whether modal is open */
  isOpen: boolean;
  /** Close handler */
  onClose: () => void;
  /** Modal title */
  title: string;
  /** Form fields */
  fields: FieldConfig[];
  /** Form data */
  formData: any;
  /** Form data change handler */
  onChange: (data: any) => void;
  /** Submit handler */
  onSubmit: (e: React.FormEvent) => void;
  /** Context for dynamic options */
  context: ConfigContext;
  /** Whether this is edit mode */
  isEdit: boolean;
  /** Is submitting */
  isSubmitting?: boolean;
  /** Show validation errors */
  showErrors?: boolean;
}

export const CrudModal: React.FC<CrudModalProps> = ({
  isOpen,
  onClose,
  title,
  fields,
  formData,
  onChange,
  onSubmit,
  context,
  isEdit,
  isSubmitting = false,
  showErrors = false
}) => {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size="lg"
      preventBackdropClose={isSubmitting}
    >
      <CrudForm
        fields={fields}
        formData={formData}
        onChange={onChange}
        onSubmit={onSubmit}
        onCancel={onClose}
        context={context}
        isEdit={isEdit}
        showErrors={showErrors}
        isSubmitting={isSubmitting}
      />
    </Modal>
  );
};
