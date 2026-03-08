import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  BookOpenIcon,
  CheckCircleIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  TrashIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline';
import { ErrorMessage, LoadingSpinner, PageHeader } from './components/common';
import { useKnowledgeBases } from './hooks/useKnowledgeBases';
import type { KnowledgeBase } from '../../types/knowledgeBase';

function formatDate(value?: string): string {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
}

function formatCount(value: number): string {
  return new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

function hasCustomRetrievalSettings(item: KnowledgeBase): boolean {
  return Boolean(item.embedding_model || item.chunk_size || item.chunk_overlap);
}

export const KnowledgeBasesPage: React.FC = () => {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const kbHook = useKnowledgeBases();
  const [query, setQuery] = useState('');
  const isZh = i18n.language.toLowerCase().startsWith('zh');

  const copy = isZh
    ? {
        title: '知识库配置',
        description: '为不同资料建立独立知识库，并管理它们的文档与检索参数。',
        create: '新建知识库',
        globalRag: '全局 RAG 设置',
        searchPlaceholder: '按名称、ID 或描述搜索知识库',
        total: '知识库',
        enabled: '已启用',
        documents: '文档总数',
        customized: '自定义参数',
        emptyTitle: '还没有知识库',
        emptyDescription: '先创建一个知识库，后续再上传文档并绑定助手。',
        noSearchTitle: '没有找到匹配的知识库',
        noSearchDescription: '换个关键词试试，或者直接新建一个知识库。',
        manage: '管理',
        enable: '启用',
        disable: '停用',
        delete: '删除',
        usesGlobal: '继承全局默认',
        docsCount: '文档',
        createdAt: '创建于',
        retrieval: '检索配置',
        nextAction: '建议操作',
        nextUpload: '上传文档',
        nextEnable: '启用知识库',
        nextBind: '绑定到助手',
        summaryNoDocs: '还没有文档',
        summaryCustomized: '已覆盖默认参数',
        summaryDefault: '使用全局默认参数',
        statusEnabled: '已启用',
        statusDisabled: '未启用',
        deleteConfirm: (name: string) => `确定删除知识库“${name}”吗？此操作会移除其中的文档。`,
      }
    : {
        title: 'Knowledge Base Settings',
        description: 'Create separate knowledge bases for different materials, then manage their documents and retrieval settings.',
        create: 'New knowledge base',
        globalRag: 'Global RAG settings',
        searchPlaceholder: 'Search by name, ID, or description',
        total: 'Knowledge bases',
        enabled: 'Enabled',
        documents: 'Documents',
        customized: 'Custom overrides',
        emptyTitle: 'No knowledge bases yet',
        emptyDescription: 'Create your first knowledge base, then upload documents and bind it to assistants.',
        noSearchTitle: 'No matching knowledge bases',
        noSearchDescription: 'Try another keyword or create a new knowledge base.',
        manage: 'Manage',
        enable: 'Enable',
        disable: 'Disable',
        delete: 'Delete',
        usesGlobal: 'Using global defaults',
        docsCount: 'docs',
        createdAt: 'Created',
        retrieval: 'Retrieval',
        nextAction: 'Next step',
        nextUpload: 'Upload documents',
        nextEnable: 'Enable knowledge base',
        nextBind: 'Bind to assistant',
        summaryNoDocs: 'No documents yet',
        summaryCustomized: 'Overrides enabled',
        summaryDefault: 'Using global defaults',
        statusEnabled: 'Enabled',
        statusDisabled: 'Disabled',
        deleteConfirm: (name: string) => `Delete knowledge base "${name}"? This also removes its documents.`,
      };

  const knowledgeBases = useMemo(() => {
    return [...kbHook.knowledgeBases].sort((a, b) => {
      if (a.enabled !== b.enabled) {
        return a.enabled ? -1 : 1;
      }
      if (a.document_count !== b.document_count) {
        return b.document_count - a.document_count;
      }
      return a.name.localeCompare(b.name);
    });
  }, [kbHook.knowledgeBases]);

  const filteredKnowledgeBases = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return knowledgeBases;
    return knowledgeBases.filter((item) => [item.name, item.id, item.description ?? ''].some((value) => value.toLowerCase().includes(normalized)));
  }, [knowledgeBases, query]);

  const stats = useMemo(() => {
    return {
      total: knowledgeBases.length,
      enabled: knowledgeBases.filter((item) => item.enabled).length,
      documents: knowledgeBases.reduce((sum, item) => sum + (item.document_count || 0), 0),
      customized: knowledgeBases.filter(hasCustomRetrievalSettings).length,
    };
  }, [knowledgeBases]);

  const handleDelete = async (item: KnowledgeBase) => {
    if (!window.confirm(copy.deleteConfirm(item.name || item.id))) {
      return;
    }

    try {
      await kbHook.deleteKnowledgeBase(item.id);
    } catch (error) {
      console.error('Delete knowledge base failed:', error);
    }
  };

  const handleToggleEnabled = async (item: KnowledgeBase) => {
    try {
      await kbHook.updateKnowledgeBase(item.id, { enabled: !item.enabled });
    } catch (error) {
      console.error('Toggle knowledge base failed:', error);
    }
  };

  if (kbHook.loading) {
    return <LoadingSpinner message={isZh ? '正在加载知识库...' : 'Loading knowledge bases...'} />;
  }

  if (kbHook.error) {
    return <ErrorMessage message={kbHook.error} onRetry={kbHook.refreshData} />;
  }

  return (
    <div className="space-y-6" data-name="knowledge-bases-page">
      <PageHeader
        title={copy.title}
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
              onClick={() => navigate('/settings/knowledge-bases/new')}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
            >
              <PlusIcon className="h-4 w-4" />
              {copy.create}
            </button>
          </div>
        )}
      />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-name="knowledge-bases-stats">
        {[
          { label: copy.total, value: stats.total, icon: BookOpenIcon },
          { label: copy.enabled, value: stats.enabled, icon: CheckCircleIcon },
          { label: copy.documents, value: stats.documents, icon: BookOpenIcon },
          { label: copy.customized, value: stats.customized, icon: WrenchScrewdriverIcon },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-4 dark:border-gray-700 dark:bg-gray-900/50">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-medium uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">{item.label}</div>
                  <div className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{formatCount(item.value)}</div>
                </div>
                <div className="rounded-lg bg-white p-2 text-gray-500 dark:bg-gray-800 dark:text-gray-300">
                  <Icon className="h-5 w-5" />
                </div>
              </div>
            </div>
          );
        })}
      </section>

      <section className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/50" data-name="knowledge-bases-toolbar">
        <label className="relative block" htmlFor="knowledge-base-search">
          <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            id="knowledge-base-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={copy.searchPlaceholder}
            className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-4 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
        </label>
      </section>

      {filteredKnowledgeBases.length === 0 ? (
        <section className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-6 py-12 text-center dark:border-gray-600 dark:bg-gray-900/40">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-white text-gray-500 dark:bg-gray-800 dark:text-gray-300">
            <BookOpenIcon className="h-6 w-6" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-gray-900 dark:text-white">
            {knowledgeBases.length === 0 ? copy.emptyTitle : copy.noSearchTitle}
          </h3>
          <p className="mx-auto mt-2 max-w-xl text-sm text-gray-500 dark:text-gray-400">
            {knowledgeBases.length === 0 ? copy.emptyDescription : copy.noSearchDescription}
          </p>
        </section>
      ) : (
        <section className="grid gap-4 xl:grid-cols-2" data-name="knowledge-base-card-grid">
          {filteredKnowledgeBases.map((item) => {
            const nextStep = item.document_count === 0 ? copy.nextUpload : item.enabled ? copy.nextBind : copy.nextEnable;
            const retrievalSummary = hasCustomRetrievalSettings(item) ? copy.summaryCustomized : copy.summaryDefault;

            return (
              <article
                key={item.id}
                className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md dark:border-gray-700 dark:bg-gray-900"
                data-name="knowledge-base-card"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate text-xl font-semibold text-gray-900 dark:text-white">{item.name}</h3>
                      <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${item.enabled ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200' : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200'}`}>
                        {item.enabled ? copy.statusEnabled : copy.statusDisabled}
                      </span>
                    </div>
                    <div className="mt-2 truncate text-xs font-medium uppercase tracking-[0.16em] text-gray-400 dark:text-gray-500">{item.id}</div>
                    <p className="mt-3 line-clamp-2 text-sm leading-6 text-gray-600 dark:text-gray-300">
                      {item.description || retrievalSummary}
                    </p>
                  </div>
                  <div className="shrink-0 rounded-xl bg-gray-50 px-3 py-2 text-right dark:bg-gray-800">
                    <div className="text-2xl font-semibold text-gray-900 dark:text-white">{formatCount(item.document_count || 0)}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{copy.docsCount}</div>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                    {copy.createdAt} {formatDate(item.created_at)}
                  </span>
                  <span className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                    {copy.retrieval}: {retrievalSummary}
                  </span>
                  {item.document_count === 0 && (
                    <span className="rounded-full bg-amber-50 px-3 py-1 text-xs text-amber-700 dark:bg-amber-500/10 dark:text-amber-200">
                      {copy.summaryNoDocs}
                    </span>
                  )}
                </div>

                <div className="mt-5 flex items-center justify-between gap-4 border-t border-gray-200 pt-4 dark:border-gray-700">
                  <div>
                    <div className="text-xs font-medium uppercase tracking-[0.16em] text-gray-400 dark:text-gray-500">{copy.nextAction}</div>
                    <div className="mt-1 text-sm font-medium text-gray-700 dark:text-gray-200">{nextStep}</div>
                  </div>
                  <div className="flex flex-wrap justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => navigate(`/settings/knowledge-bases/${item.id}`)}
                      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
                    >
                      {copy.manage}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleToggleEnabled(item)}
                      className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
                    >
                      {item.enabled ? copy.disable : copy.enable}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(item)}
                      className="inline-flex items-center gap-2 rounded-lg border border-rose-300 px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50 dark:border-rose-800 dark:text-rose-300 dark:hover:bg-rose-950/40"
                    >
                      <TrashIcon className="h-4 w-4" />
                      {copy.delete}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
};
