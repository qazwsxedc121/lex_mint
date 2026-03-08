import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeftIcon, CheckBadgeIcon, PlusIcon } from '@heroicons/react/24/outline';
import { ErrorMessage, LoadingSpinner } from './components/common';
import { KnowledgeBaseFormSections } from './components/KnowledgeBaseFormSections';
import { knowledgeBasesConfig } from './config';
import { useKnowledgeBases } from './hooks/useKnowledgeBases';
import type { KnowledgeBaseCreate } from '../../types/knowledgeBase';

function buildInitialFormData(): Record<string, any> {
  const data: Record<string, any> = {};

  knowledgeBasesConfig.createFields.forEach((field) => {
    if (data[field.name] === undefined && 'defaultValue' in field) {
      data[field.name] = field.defaultValue;
    }
  });
  return data;
}

export const KnowledgeBaseCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const kbHook = useKnowledgeBases();
  const [formData, setFormData] = useState<Record<string, any>>(buildInitialFormData);
  const [showErrors, setShowErrors] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isZh = i18n.language.toLowerCase().startsWith('zh');

  const copy = isZh
    ? {
        eyebrow: 'Create Knowledge Base',
        title: '先定义这个知识库要装什么资料',
        description: '这里先只做一件事：把知识库的边界和默认检索方式说清楚。文档上传会在创建后进入下一步。',
        back: '返回列表',
        create: '创建知识库',
        creating: '创建中...',
        summary: '创建预览',
        tips: '创建建议',
        after: '创建后会发生什么',
        idLabel: '知识库 ID',
        nameLabel: '显示名称',
        statusLabel: '状态',
        statusEnabled: '创建后立即启用',
        statusDisabled: '先保留为未启用',
        advancedLabel: '检索参数',
        globalDefaults: '先继承全局默认',
        customOverrides: '创建时直接覆盖参数',
        tipsList: [
          '如果资料类型比较单一，优先一个知识库只放一类文档。',
          'ID 建议稳定、短小、便于后续绑定助手和排查问题。',
          '不确定 chunk 参数时，先继承全局默认，后面再按实际效果微调。',
        ],
        afterList: [
          '创建成功后会跳回列表页。',
          '接着进入知识库详情页上传文档。',
          '最后再把这个知识库绑定到需要的助手。',
        ],
        requiredField: (field: string) => `请先填写${field}`,
      }
    : {
        eyebrow: 'Create Knowledge Base',
        title: 'Define what this knowledge base should contain',
        description: 'Start by setting the scope and retrieval defaults. Document upload happens in the next step after creation.',
        back: 'Back to list',
        create: 'Create knowledge base',
        creating: 'Creating...',
        summary: 'Preview',
        tips: 'Recommendations',
        after: 'What happens next',
        idLabel: 'Knowledge base ID',
        nameLabel: 'Display name',
        statusLabel: 'Status',
        statusEnabled: 'Enable immediately after creation',
        statusDisabled: 'Keep disabled for now',
        advancedLabel: 'Retrieval settings',
        globalDefaults: 'Use global defaults first',
        customOverrides: 'Override settings during creation',
        tipsList: [
          'Keep one knowledge base focused on one document domain when possible.',
          'Choose a stable, short ID so assistant bindings stay predictable.',
          'If you are unsure about chunk settings, inherit the global defaults first and tune later.',
        ],
        afterList: [
          'You will return to the list page after creation.',
          'Then open the detail page to upload documents.',
          'Finally bind the knowledge base to the assistants that need it.',
        ],
        requiredField: (field: string) => `Please fill in ${field}`,
      };

  const hasAdvancedOverrides = useMemo(() => {
    return Boolean(formData.embedding_model || formData.chunk_size || formData.chunk_overlap);
  }, [formData.embedding_model, formData.chunk_overlap, formData.chunk_size]);

  const handleBack = () => {
    if (isSubmitting) return;
    navigate('/settings/knowledge-bases');
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setShowErrors(true);

    for (const field of knowledgeBasesConfig.createFields) {
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
      await kbHook.createKnowledgeBase(formData as KnowledgeBaseCreate);
      navigate('/settings/knowledge-bases', { replace: true });
    } catch (error) {
      console.error('Create knowledge base failed:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (kbHook.loading) {
    return <LoadingSpinner message={isZh ? '正在准备知识库配置...' : 'Preparing knowledge base form...'} />;
  }

  if (kbHook.error) {
    return <ErrorMessage message={kbHook.error} onRetry={kbHook.refreshData} />;
  }

  return (
    <div className="space-y-6" data-name="knowledge-base-create-page">
      <section
        className="overflow-hidden rounded-[28px] border border-teal-200/70 bg-[radial-gradient(circle_at_top_right,_rgba(45,212,191,0.24),_transparent_30%),linear-gradient(135deg,_#f8fffe_0%,_#ffffff_58%,_#fefce8_100%)] p-6 shadow-sm dark:border-teal-400/20 dark:bg-[radial-gradient(circle_at_top_right,_rgba(20,184,166,0.22),_transparent_30%),linear-gradient(135deg,_rgba(15,23,42,1)_0%,_rgba(17,24,39,1)_58%,_rgba(120,53,15,0.35)_100%)]"
        data-name="knowledge-base-create-hero"
      >
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-teal-700 dark:text-teal-300">
              {copy.eyebrow}
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">
              {copy.title}
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
              {copy.description}
            </p>
          </div>
          <button
            type="button"
            onClick={handleBack}
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 self-start rounded-full border border-slate-300 bg-white/80 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-600 dark:bg-slate-900/50 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            <ArrowLeftIcon className="h-4 w-4" />
            {copy.back}
          </button>
        </div>
      </section>

      <form onSubmit={handleSubmit} className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]" data-name="knowledge-base-create-form">
        <div className="space-y-6">
          <KnowledgeBaseFormSections
            fields={knowledgeBasesConfig.createFields}
            formData={formData}
            onChange={setFormData}
            showErrors={showErrors}
          />

          <div className="flex flex-wrap items-center justify-end gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <button
              type="button"
              onClick={handleBack}
              disabled={isSubmitting}
              className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              {copy.back}
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-teal-400 dark:text-slate-950 dark:hover:bg-teal-300"
            >
              <PlusIcon className="h-4 w-4" />
              {isSubmitting ? copy.creating : copy.create}
            </button>
          </div>
        </div>

        <aside className="space-y-4" data-name="knowledge-base-create-sidebar">
          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">{copy.summary}</div>
            <div className="mt-4 space-y-4">
              <div>
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-slate-400">{copy.nameLabel}</div>
                <div className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{formData.name || '-'}</div>
              </div>
              <div>
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-slate-400">{copy.idLabel}</div>
                <div className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{formData.id || '-'}</div>
              </div>
              <div>
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-slate-400">{copy.statusLabel}</div>
                <div className="mt-2 text-sm font-medium text-slate-900 dark:text-white">
                  {formData.enabled !== false ? copy.statusEnabled : copy.statusDisabled}
                </div>
              </div>
              <div>
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-slate-400">{copy.advancedLabel}</div>
                <div className="mt-2 text-sm font-medium text-slate-900 dark:text-white">
                  {hasAdvancedOverrides ? copy.customOverrides : copy.globalDefaults}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="inline-flex rounded-xl bg-emerald-50 p-2 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200">
              <CheckBadgeIcon className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-slate-900 dark:text-white">{copy.tips}</h3>
            <div className="mt-4 space-y-3">
              {copy.tipsList.map((item) => (
                <div key={item} className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                  {item}
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{copy.after}</h3>
            <div className="mt-4 space-y-3">
              {copy.afterList.map((item) => (
                <div key={item} className="rounded-2xl border border-dashed border-slate-300 p-4 text-sm leading-6 text-slate-700 dark:border-slate-600 dark:text-slate-200">
                  {item}
                </div>
              ))}
            </div>
          </div>
        </aside>
      </form>
    </div>
  );
};
