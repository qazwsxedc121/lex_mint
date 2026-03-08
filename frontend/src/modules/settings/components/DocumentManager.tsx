import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowPathIcon, DocumentArrowUpIcon, TrashIcon } from '@heroicons/react/24/outline';
import { SettingsHelp } from './common';
import * as api from '../../../services/api';
import type { KnowledgeBaseDocument } from '../../../types/knowledgeBase';

const ACCEPTED_TYPES = '.txt,.md,.pdf,.docx,.html';
const PAGE_SIZE = 100;

interface DocumentManagerProps {
  kbId: string;
  onDocumentsChanged?: (documents: KnowledgeBaseDocument[]) => void;
}

interface UploadProgressState {
  total: number;
  completed: number;
  failed: number;
  currentFile: string;
  currentFilePercent: number;
  overallPercent: number;
}

const statusConfig: Record<string, { labelKey: string; className: string }> = {
  pending: {
    labelKey: 'documents.pending',
    className: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  },
  processing: {
    labelKey: 'documents.processing',
    className: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  },
  ready: {
    labelKey: 'documents.ready',
    className: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  },
  error: {
    labelKey: 'documents.error',
    className: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
  },
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const DocumentManager: React.FC<DocumentManagerProps> = ({ kbId, onDocumentsChanged }) => {
  const { t, i18n } = useTranslation('settings');
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgressState | null>(null);
  const [reprocessingAll, setReprocessingAll] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isZh = i18n.language.toLowerCase().startsWith('zh');

  const summaryLabels = isZh
    ? { total: '总文档', ready: '已就绪', processing: '处理中', error: '异常', page: '当前页', prev: '上一页', next: '下一页' }
    : { total: 'Total', ready: 'Ready', processing: 'Processing', error: 'Errors', page: 'Page', prev: 'Previous', next: 'Next' };

  const syncDocuments = useCallback((docs: KnowledgeBaseDocument[]) => {
    setDocuments(docs);
    onDocumentsChanged?.(docs);
  }, [onDocumentsChanged]);

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await api.listDocuments(kbId);
      syncDocuments(docs);

      const hasProcessing = docs.some((doc) => doc.status === 'pending' || doc.status === 'processing');
      if (hasProcessing && !pollingRef.current) {
        pollingRef.current = setInterval(async () => {
          try {
            const updated = await api.listDocuments(kbId);
            syncDocuments(updated);
            const stillProcessing = updated.some((doc) => doc.status === 'pending' || doc.status === 'processing');
            if (!stillProcessing && pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
          } catch {
            // Ignore polling errors.
          }
        }, 3000);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t('documents.failedToLoad');
      setError(message);
    }
  }, [kbId, syncDocuments, t]);

  useEffect(() => {
    setLoading(true);
    loadDocuments().finally(() => setLoading(false));
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [loadDocuments]);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(documents.length / PAGE_SIZE));
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, documents.length]);

  const summaryStats = useMemo(() => ({
    total: documents.length,
    ready: documents.filter((doc) => doc.status === 'ready').length,
    processing: documents.filter((doc) => doc.status === 'pending' || doc.status === 'processing').length,
    error: documents.filter((doc) => doc.status === 'error').length,
  }), [documents]);

  const totalPages = Math.max(1, Math.ceil(documents.length / PAGE_SIZE));
  const visibleDocuments = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return documents.slice(start, start + PAGE_SIZE);
  }, [currentPage, documents]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    const uploadQueue = Array.from(files);
    setUploading(true);
    setUploadProgress({
      total: uploadQueue.length,
      completed: 0,
      failed: 0,
      currentFile: uploadQueue[0]?.name || '',
      currentFilePercent: 0,
      overallPercent: 0,
    });
    setError(null);

    let successCount = 0;
    let failedCount = 0;
    const failedFiles: string[] = [];

    try {
      for (const [index, file] of uploadQueue.entries()) {
        setUploadProgress((prev) => prev ? {
          ...prev,
          currentFile: file.name,
          currentFilePercent: 0,
          overallPercent: Math.max(prev.overallPercent, Math.round((index / uploadQueue.length) * 100)),
        } : prev);

        try {
          await api.uploadDocument(kbId, file, (percent) => {
            setUploadProgress((prev) => {
              if (!prev) return prev;
              const currentPercent = Math.max(0, Math.min(100, Math.round(percent)));
              const doneCount = successCount + failedCount;
              const overallPercent = Math.min(100, Math.round(((doneCount + currentPercent / 100) / uploadQueue.length) * 100));
              return { ...prev, currentFile: file.name, currentFilePercent: currentPercent, overallPercent };
            });
          });
          successCount += 1;
        } catch {
          failedCount += 1;
          failedFiles.push(file.name);
        } finally {
          setUploadProgress((prev) => prev ? {
            ...prev,
            completed: successCount,
            failed: failedCount,
            currentFilePercent: 100,
            overallPercent: Math.min(100, Math.round(((successCount + failedCount) / uploadQueue.length) * 100)),
          } : prev);
        }
      }

      await loadDocuments();
      setCurrentPage(1);
      if (failedCount > 0) {
        setError(t('documents.uploadFailedSome', { count: failedCount, files: failedFiles.join(', ') }));
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t('documents.uploadFailed');
      setError(message);
    } finally {
      setUploading(false);
      setUploadProgress(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm(t('documents.confirmDelete'))) return;
    try {
      await api.deleteDocument(kbId, docId);
      await loadDocuments();
    } catch (err) {
      const message = err instanceof Error ? err.message : t('documents.failedToDelete');
      setError(message);
    }
  };

  const handleDeleteAll = async () => {
    if (documents.length === 0) {
      setError(t('documents.noDocsForDelete'));
      return;
    }
    if (!confirm(t('documents.confirmDeleteAll', { count: documents.length }))) {
      return;
    }

    setDeletingAll(true);
    setError(null);
    let failed = 0;
    try {
      for (const doc of documents) {
        try {
          await api.deleteDocument(kbId, doc.id);
        } catch {
          failed += 1;
        }
      }
      await loadDocuments();
      setCurrentPage(1);
      if (failed > 0) {
        setError(t('documents.failedToDeleteSome', { count: failed }));
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t('documents.failedToDeleteAll');
      setError(message);
    } finally {
      setDeletingAll(false);
    }
  };

  const handleReprocess = async (docId: string) => {
    try {
      await api.reprocessDocument(kbId, docId);
      await loadDocuments();
    } catch (err) {
      const message = err instanceof Error ? err.message : t('documents.failedToReprocess');
      setError(message);
    }
  };

  const handleReprocessAll = async () => {
    const candidates = documents.filter((doc) => doc.status !== 'processing');
    if (candidates.length === 0) {
      setError(t('documents.noDocsForReprocess'));
      return;
    }
    if (!confirm(t('documents.confirmReprocessAll'))) {
      return;
    }

    setReprocessingAll(true);
    setError(null);
    try {
      for (const doc of candidates) {
        await api.reprocessDocument(kbId, doc.id);
      }
      await loadDocuments();
    } catch (err) {
      const message = err instanceof Error ? err.message : t('documents.failedToReprocessAll');
      setError(message);
    } finally {
      setReprocessingAll(false);
    }
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    if (uploading) return;
    handleUpload(event.dataTransfer.files);
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
  };

  return (
    <div data-name="document-manager" className="mt-6">
      <div className="mb-4 flex items-center justify-between gap-3" data-name="document-manager-header">
        <h3 className="inline-flex items-center gap-2 text-lg font-medium text-gray-900 dark:text-white">
          <span>{t('documents.title')}</span>
          <SettingsHelp
            help={{
              openTitle: t('documents.help.openTitle'),
              title: t('documents.help.title'),
              size: 'xl',
              sections: [
                {
                  title: t('documents.help.quickStartTitle'),
                  items: [
                    t('documents.help.quickStartItem1'),
                    t('documents.help.quickStartItem2'),
                    t('documents.help.quickStartItem3'),
                  ],
                },
                {
                  title: t('documents.help.pitfallsTitle'),
                  items: [
                    t('documents.help.pitfallsItem1'),
                    t('documents.help.pitfallsItem2'),
                    t('documents.help.pitfallsItem3'),
                  ],
                },
              ],
            }}
            triggerDataName="documents-help-trigger"
            contentDataName="documents-help-content"
          />
        </h3>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleReprocessAll}
            disabled={reprocessingAll || deletingAll || documents.length === 0}
            className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
          >
            <ArrowPathIcon className="h-4 w-4" />
            {reprocessingAll ? t('documents.reprocessing') : t('documents.reprocessAll')}
          </button>
          <button
            type="button"
            onClick={handleDeleteAll}
            disabled={deletingAll || reprocessingAll || documents.length === 0}
            className="inline-flex items-center gap-2 rounded-md border border-red-300 bg-white px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-60 dark:border-red-800 dark:bg-gray-700 dark:text-red-300 dark:hover:bg-red-900/20"
          >
            <TrashIcon className="h-4 w-4" />
            {deletingAll ? t('documents.deletingAll') : t('documents.deleteAll')}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-name="document-manager-summary">
        {[
          { label: summaryLabels.total, value: summaryStats.total },
          { label: summaryLabels.ready, value: summaryStats.ready },
          { label: summaryLabels.processing, value: summaryStats.processing },
          { label: summaryLabels.error, value: summaryStats.error },
        ].map((item) => (
          <div key={item.label} className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/80">
            <div className="text-xs font-medium uppercase tracking-[0.16em] text-gray-400 dark:text-gray-500">{item.label}</div>
            <div className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{item.value}</div>
          </div>
        ))}
      </div>

      <div
        className={`mb-4 rounded-lg border-2 border-dashed border-gray-300 p-6 text-center transition-colors dark:border-gray-600 ${uploading ? 'cursor-not-allowed opacity-70' : 'cursor-pointer hover:border-blue-400 dark:hover:border-blue-500'}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onClick={() => {
          if (!uploading) fileInputRef.current?.click();
        }}
      >
        <DocumentArrowUpIcon className="mx-auto mb-2 h-8 w-8 text-gray-400 dark:text-gray-500" />
        <p className="text-sm text-gray-600 dark:text-gray-400">{uploading ? t('documents.uploading') : t('documents.dropOrClick')}</p>
        {uploading && uploadProgress && (
          <div data-name="upload-progress" className="mt-3 space-y-2 text-left">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {t('documents.currentFileProgress', { name: uploadProgress.currentFile, percent: uploadProgress.currentFilePercent })}
              </p>
              <progress className="mt-1 h-2 w-full overflow-hidden rounded bg-gray-200 dark:bg-gray-700" value={uploadProgress.currentFilePercent} max={100} />
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {uploadProgress.failed > 0
                  ? t('documents.batchProgressWithFailed', { done: uploadProgress.completed, total: uploadProgress.total, overall: uploadProgress.overallPercent, failed: uploadProgress.failed })
                  : t('documents.batchProgress', { done: uploadProgress.completed, total: uploadProgress.total, overall: uploadProgress.overallPercent })}
              </p>
              <progress className="mt-1 h-2 w-full overflow-hidden rounded bg-gray-200 dark:bg-gray-700" value={uploadProgress.overallPercent} max={100} />
            </div>
          </div>
        )}
        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{t('documents.supportedTypes')}</p>
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_TYPES}
          multiple
          disabled={uploading}
          className="hidden"
          onChange={(event) => handleUpload(event.target.files)}
        />
      </div>

      {loading ? (
        <div className="py-8 text-center text-gray-500 dark:text-gray-400">{t('documents.loadingDocs')}</div>
      ) : documents.length === 0 ? (
        <div className="py-8 text-center text-gray-500 dark:text-gray-400">{t('documents.noDocuments')}</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">{t('documents.filename')}</th>
                <th className="hidden px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 sm:table-cell">{t('documents.type')}</th>
                <th className="hidden px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 sm:table-cell">{t('documents.size')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">{t('common:status')}</th>
                <th className="hidden px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 sm:table-cell">{t('documents.chunks')}</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">{t('common:actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white dark:divide-gray-700 dark:bg-gray-900">
              {visibleDocuments.map((doc) => {
                const status = statusConfig[doc.status] || statusConfig.pending;
                return (
                  <tr key={doc.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-white">
                      <div className="max-w-[320px] truncate" title={doc.filename}>{doc.filename}</div>
                      {doc.error_message && (
                        <div className="max-w-[320px] truncate text-xs text-red-500 dark:text-red-400" title={doc.error_message}>{doc.error_message}</div>
                      )}
                    </td>
                    <td className="hidden px-4 py-3 text-sm text-gray-500 dark:text-gray-400 sm:table-cell">{doc.file_type}</td>
                    <td className="hidden px-4 py-3 text-sm text-gray-500 dark:text-gray-400 sm:table-cell">{formatFileSize(doc.file_size)}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${status.className}`}>
                        {doc.status === 'processing' && (
                          <svg className="-ml-0.5 mr-1.5 h-3 w-3 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                        )}
                        {t(status.labelKey)}
                      </span>
                    </td>
                    <td className="hidden px-4 py-3 text-sm text-gray-500 dark:text-gray-400 sm:table-cell">{doc.chunk_count || '-'}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end space-x-2">
                        <button
                          type="button"
                          onClick={() => handleReprocess(doc.id)}
                          className="p-1 text-gray-400 transition-colors hover:text-blue-600 dark:hover:text-blue-400"
                          title={t('documents.reprocess')}
                          disabled={doc.status === 'processing' || deletingAll}
                        >
                          <ArrowPathIcon className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(doc.id)}
                          className="p-1 text-gray-400 transition-colors hover:text-red-600 dark:hover:text-red-400"
                          title={t('common:delete')}
                          disabled={deletingAll}
                        >
                          <TrashIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 px-4 py-3 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
              <div>{summaryLabels.page} {currentPage} / {totalPages}</div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                  disabled={currentPage === 1}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                  {summaryLabels.prev}
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                  disabled={currentPage === totalPages}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                  {summaryLabels.next}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
