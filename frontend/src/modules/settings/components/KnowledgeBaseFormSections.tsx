import React from 'react';
import { useTranslation } from 'react-i18next';
import { FormField } from './common';
import type { ConfigContext, FieldConfig } from '../config/types';

interface KnowledgeBaseFormSectionsProps {
  fields: FieldConfig[];
  formData: Record<string, any>;
  onChange: (data: Record<string, any>) => void;
  context?: ConfigContext;
  showErrors?: boolean;
}

const BASIC_FIELD_NAMES = ['id', 'name', 'description', 'enabled'];
const ADVANCED_FIELD_NAMES = ['embedding_model', 'chunk_size', 'chunk_overlap'];

export const KnowledgeBaseFormSections: React.FC<KnowledgeBaseFormSectionsProps> = ({
  fields,
  formData,
  onChange,
  context = {},
  showErrors = false,
}) => {
  const { i18n } = useTranslation();
  const isZh = i18n.language.toLowerCase().startsWith('zh');

  const basicFields = fields.filter((field) => BASIC_FIELD_NAMES.includes(field.name));
  const advancedFields = fields.filter((field) => ADVANCED_FIELD_NAMES.includes(field.name));

  const renderField = (field: FieldConfig) => (
    <FormField
      key={field.name}
      config={field}
      value={formData[field.name]}
      onChange={(value) => onChange({ ...formData, [field.name]: value })}
      formData={formData}
      context={context}
      showErrors={showErrors}
    />
  );

  return (
    <div className="space-y-6" data-name="knowledge-base-form-sections">
      <section
        className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900"
        data-name="knowledge-base-basic-section"
      >
        <div className="mb-5">
          <div>
            <h3 className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
              {isZh ? '基础信息' : 'Basic information'}
            </h3>
            <p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-300">
              {isZh
                ? '设置知识库名称、标识和说明。这里的配置决定这个知识库如何被识别和使用。'
                : 'Set the name, identifier, and description used to recognize this knowledge base.'}
            </p>
          </div>
        </div>
        <div className="space-y-4">{basicFields.map(renderField)}</div>
      </section>

      <section
        className="rounded-2xl border border-slate-200 bg-slate-50/70 p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900/70"
        data-name="knowledge-base-advanced-section"
      >
        <div className="mb-5">
          <h3 className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
            {isZh ? '检索参数覆盖' : 'Retrieval overrides'}
          </h3>
          <p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-300">
            {isZh
              ? '默认情况下直接继承全局 RAG 设置。只有当前知识库需要独立分块或嵌入模型时，再单独覆盖。'
              : 'Keep the global RAG defaults unless this knowledge base needs its own chunking or embedding settings.'}
          </p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">{advancedFields.map(renderField)}</div>
      </section>
    </div>
  );
};
