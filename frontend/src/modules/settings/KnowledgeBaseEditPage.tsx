import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeftIcon, DocumentTextIcon, WrenchScrewdriverIcon } from '@heroicons/react/24/outline';
import { ErrorMessage, LoadingSpinner, PageHeader, SuccessMessage } from './components/common';
import { KnowledgeBaseFormSections } from './components/KnowledgeBaseFormSections';
import { DocumentManager } from './components/DocumentManager';
import { knowledgeBasesConfig } from './config';
import { useKnowledgeBases } from './hooks/useKnowledgeBases';
import type { KnowledgeBase, KnowledgeBaseDocument, KnowledgeBaseUpdate } from '../../types/knowledgeBase';

function hasCustomOverrides(item: KnowledgeBase | Record<string, any>): boolean {
  return Boolean(item.embedding_model || item.chunk_size || item.chunk_overlap);
}

export const KnowledgeBaseEditPage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const kbHook = useKnowledgeBases();
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [showErrors, setShowErrors] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const isZh = i18n.language.toLowerCase().startsWith('zh');

  const copy = isZh
    ? {
        titleFallback: '知识库设置',
        description: '管理这个知识库的基础信息、检索参数和文档内容。',
        back: '返回列表',
        globalRag: '全局 RAG 设置',
        save: '保存变更',
        saving: '保存中...',
        updated: '知识库已更新',
        notFound: '未找到对应的知识库',
        requiredField: (field: string) => `请先填写${field}`,
        documents: '文档数',
        status: '状态',
        overrides: '参数覆盖',
        enabled: '已启用',
        disabled: '未启用',
        overridesYes: '已自定义',
        overridesNo: '继承全局默认',
        saveHint: '修改表单后记得保存；文档上传和重处理会在下方直接生效。',
        docsTitle: '文档与索引',
        docsDescription: '上传文档、查看处理状态，并在需要时重新处理或删除文档。',
      }
    : {
        titleFallback: 'Knowledge Base Settings',
        description: 'Manage the core settings, retrieval overrides, and documents for this knowledge base.',
        back: 'Back to list',
        globalRag: 'Global RAG settings',
        save: 'Save changes',
        saving: 'Saving...',
        updated: 'Knowledge base updated',
        notFound: 'Knowledge base not found',
        requiredField: (field: string) => `Please fill in ${field}`,
        documents: 'Documents',
        status: 'Status',
        overrides: 'Overrides',
        enabled: 'Enabled',
        disabled: 'Disabled',
        overridesYes: 'Customized',
        overridesNo: 'Using global defaults',
        saveHint: 'Remember to save form changes. Document uploads and reprocessing below take effect directly.',
        docsTitle: 'Documents and indexing',
        docsDescription: 'Upload files, review processing status, and reprocess or remove documents when needed.',
      };

  const fields = knowledgeBasesConfig.editFields || knowledgeBasesConfig.createFields;

  const item = useMemo(
    () => kbHook.knowledgeBases.find((kb: KnowledgeBase) => kb.id === kbId),
    [kbHook.knowledgeBases, kbId]
  );

  useEffect(() => {
    if (!item) return;

    const data: Record<string, any> = { ...item };
    fields.forEach((field) => {
      if (data[field.name] === undefined && 'defaultValue' in field) {
        data[field.name] = field.defaultValue;
      }
    });

    setFormData(data);
  }, [fields, item]);

  useEffect(() => {
    if (!successMessage) return undefined;
    const timer = window.setTimeout(() => setSuccessMessage(null), 3000);
    return () => window.clearTimeout(timer);
  }, [successMessage]);

  const documentCount = documents.length > 0 ? documents.length : item?.document_count ?? 0;

  const handleBack = () => {
    if (isSubmitting) return;
    navigate('/settings/knowledge-bases');
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setShowErrors(true);

    for (const field of fields) {
      if (field.required && !formData[field.name]) {
        alert(copy.requiredField(field.label));
        return;
      }

      if (field.validate) {
        const error = field.validate(formData[field.name]);
        if (error) {
          alert(error);
          return;
        }
      }
    }

    try {
      setIsSubmitting(true);
      await kbHook.updateKnowledgeBase(kbId!, formData as KnowledgeBaseUpdate);
      setSuccessMessage(copy.updated);
    } catch (error) {
      console.error('Update knowledge base failed:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (kbHook.loading) {
    return <LoadingSpinner message={isZh ? '正在加载知识库详情...' : 'Loading knowledge base detail...'} />;
  }

  if (kbHook.error) {
    return <ErrorMessage message={kbHook.error} onRetry={kbHook.refreshData} />;
  }

  if (!item || !kbId) {
    return <ErrorMessage message={copy.notFound} onRetry={kbHook.refreshData} />;
  }

  return (
    <div className="space-y-6" data-name="knowledge-base-edit-page">
      <PageHeader
        title={formData.name || item.name || copy.titleFallback}
        description={copy.description}
        actions={(
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => navigate('/settings/rag')}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
            >
              <WrenchScrewdriverIcon className="h-4 w-4" />
              {copy.globalRag}
            </button>
            <button
              type="button"
              onClick={handleBack}
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-60 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
            >
              <ArrowLeftIcon className="h-4 w-4" />
              {copy.back}
            </button>
          </div>
        )}
      />

      <div className="flex flex-wrap gap-2" data-name="knowledge-base-meta-pills">
        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          {item.id}
        </span>
        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          {copy.documents}: {documentCount}
        </span>
        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          {copy.status}: {formData.enabled ? copy.enabled : copy.disabled}
        </span>
        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          {copy.overrides}: {hasCustomOverrides(formData) ? copy.overridesYes : copy.overridesNo}
        </span>
      </div>

      {successMessage && <SuccessMessage message={successMessage} />}

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]" data-name="knowledge-base-settings-layout">
        <form onSubmit={handleSubmit} className="space-y-6">
          <KnowledgeBaseFormSections
            fields={fields}
            formData={formData}
            onChange={setFormData}
            showErrors={showErrors}
          />

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/50">
            <p className="text-sm text-gray-500 dark:text-gray-400">{copy.saveHint}</p>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleBack}
                disabled={isSubmitting}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-60 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
              >
                {copy.back}
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-60"
              >
                {isSubmitting ? copy.saving : copy.save}
              </button>
            </div>
          </div>
        </form>

        <aside className="space-y-4" data-name="knowledge-base-settings-sidebar">
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <div className="text-xs font-medium uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">{copy.documents}</div>
            <div className="mt-2 text-3xl font-semibold text-gray-900 dark:text-white">{documentCount}</div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <div className="text-xs font-medium uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">{copy.status}</div>
            <div className="mt-2 text-lg font-semibold text-gray-900 dark:text-white">{formData.enabled ? copy.enabled : copy.disabled}</div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <div className="text-xs font-medium uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">{copy.overrides}</div>
            <div className="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
              {hasCustomOverrides(formData) ? copy.overridesYes : copy.overridesNo}
            </div>
          </div>
        </aside>
      </section>

      <section
        className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-900"
        data-name="knowledge-base-documents-section"
      >
        <div className="mb-5 flex items-start gap-4">
          <div className="inline-flex rounded-xl bg-gray-100 p-3 text-gray-700 dark:bg-gray-800 dark:text-gray-200">
            <DocumentTextIcon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{copy.docsTitle}</h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{copy.docsDescription}</p>
          </div>
        </div>
        <DocumentManager kbId={kbId} onDocumentsChanged={setDocuments} />
      </section>
    </div>
  );
};
