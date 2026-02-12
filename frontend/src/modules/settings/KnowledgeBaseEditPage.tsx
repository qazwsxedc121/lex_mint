/**
 * KnowledgeBaseEditPage - Custom edit page with DocumentManager
 *
 * Wraps the standard CRUD edit form and adds document management below.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import { useKnowledgeBases } from './hooks/useKnowledgeBases';
import { knowledgeBasesConfig } from './config';
import { DocumentManager } from './components/DocumentManager';
import type { KnowledgeBase } from '../../types/knowledgeBase';

// Import common components from the crud module
import { CrudForm } from './components/crud/CrudForm';

export const KnowledgeBaseEditPage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();
  const navigate = useNavigate();
  const kbHook = useKnowledgeBases();
  const [formData, setFormData] = useState<any>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const { t } = useTranslation('settings');

  const fields = knowledgeBasesConfig.editFields || knowledgeBasesConfig.createFields;

  const item = useMemo(
    () => kbHook.knowledgeBases.find((kb: KnowledgeBase) => kb.id === kbId),
    [kbHook.knowledgeBases, kbId]
  );

  useEffect(() => {
    if (item) {
      const data: any = { ...item };
      fields.forEach((field) => {
        if (data[field.name] === undefined && 'defaultValue' in field) {
          data[field.name] = field.defaultValue;
        }
      });
      setFormData(data);
      setShowErrors(false);
      setSuccessMessage(null);
    }
  }, [item]);

  const handleBack = () => {
    if (isSubmitting) return;
    navigate('/settings/knowledge-bases');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setShowErrors(true);

    for (const field of fields) {
      if (field.required && !formData[field.name]) {
        alert(t('crud.requiredField', { field: field.label }));
        return;
      }
    }

    try {
      setIsSubmitting(true);
      await kbHook.updateKnowledgeBase(kbId!, formData);
      setSuccessMessage(t('knowledgeBase.updatedSuccess'));
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      console.error('Submit error:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (kbHook.loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-500 dark:text-gray-400">{t('knowledgeBase.loading')}</div>
      </div>
    );
  }

  if (kbHook.error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300">
        {kbHook.error}
      </div>
    );
  }

  if (!item || !kbId) {
    return (
      <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg text-yellow-700 dark:text-yellow-300">
        {t('knowledgeBase.notFound')}
      </div>
    );
  }

  return (
    <div className="space-y-4" data-name="kb-edit-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            {t('knowledgeBase.editTitle')}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t('knowledgeBase.editingName', { name: item.name })}
          </p>
        </div>
        <button
          type="button"
          onClick={handleBack}
          disabled={isSubmitting}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600 disabled:opacity-50"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          {t('common:back')}
        </button>
      </div>

      {successMessage && (
        <div className="p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-300">
          {successMessage}
        </div>
      )}

      {/* Standard form */}
      <CrudForm
        fields={fields}
        formData={formData}
        onChange={setFormData}
        onSubmit={handleSubmit}
        onCancel={handleBack}
        context={{}}
        isEdit={true}
        showErrors={showErrors}
        isSubmitting={isSubmitting}
      />

      {/* Document Manager - below the form */}
      <DocumentManager kbId={kbId} />
    </div>
  );
};
