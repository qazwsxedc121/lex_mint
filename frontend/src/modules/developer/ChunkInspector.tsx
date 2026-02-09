/**
 * ChunkInspector - View semantic chunk results per knowledge base
 */

import React, { useEffect, useMemo, useState } from 'react';
import { listDocuments, listKnowledgeBaseChunks } from '../../services/api';
import { useKnowledgeBases } from '../settings/hooks/useKnowledgeBases';
import type { KnowledgeBaseChunk, KnowledgeBaseDocument } from '../../types/knowledgeBase';

const DEFAULT_LIMIT = 200;

export const ChunkInspector: React.FC = () => {
  const kbHook = useKnowledgeBases();
  const [selectedKb, setSelectedKb] = useState<string>('');
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<string>('');
  const [limit, setLimit] = useState<number>(DEFAULT_LIMIT);
  const [chunks, setChunks] = useState<KnowledgeBaseChunk[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);
  const [chunkError, setChunkError] = useState<string | null>(null);

  const hasKnowledgeBases = kbHook.knowledgeBases.length > 0;

  useEffect(() => {
    if (!selectedKb && hasKnowledgeBases) {
      setSelectedKb(kbHook.knowledgeBases[0].id);
    }
  }, [hasKnowledgeBases, kbHook.knowledgeBases, selectedKb]);

  useEffect(() => {
    const loadDocuments = async () => {
      if (!selectedKb) {
        setDocuments([]);
        setSelectedDoc('');
        return;
      }
      setLoadingDocs(true);
      setDocError(null);
      try {
        const data = await listDocuments(selectedKb);
        setDocuments(data);
        if (data.length === 0) {
          setSelectedDoc('');
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load documents';
        setDocError(message);
      } finally {
        setLoadingDocs(false);
      }
    };

    loadDocuments();
  }, [selectedKb]);

  const fetchChunks = async () => {
    if (!selectedKb) {
      return;
    }

    const limitValue = Math.min(2000, Math.max(1, limit || DEFAULT_LIMIT));
    setLoadingChunks(true);
    setChunkError(null);

    try {
      const data = await listKnowledgeBaseChunks(selectedKb, {
        docId: selectedDoc || undefined,
        limit: limitValue,
      });
      setChunks(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load chunks';
      setChunkError(message);
    } finally {
      setLoadingChunks(false);
    }
  };

  const chunkSummary = useMemo(() => {
    if (loadingChunks) {
      return 'Loading chunks...';
    }
    if (!selectedKb) {
      return 'Select a knowledge base to load chunks.';
    }
    if (chunks.length === 0) {
      return 'No chunks loaded yet.';
    }
    return `Loaded ${chunks.length} chunk(s).`;
  }, [chunks.length, loadingChunks, selectedKb]);

  return (
    <div className="space-y-6" data-name="chunk-inspector">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3" data-name="chunk-inspector-controls">
        <div className="lg:col-span-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-name="chunk-inspector-fields">
            <label className="block text-sm text-gray-700 dark:text-gray-300" data-name="chunk-inspector-kb">
              <span className="font-medium text-gray-900 dark:text-white">Knowledge Base</span>
              <select
                value={selectedKb}
                onChange={(event) => setSelectedKb(event.target.value)}
                className="mt-2 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
              >
                {!hasKnowledgeBases && <option value="">No knowledge bases</option>}
                {kbHook.knowledgeBases.map((kb) => (
                  <option key={kb.id} value={kb.id}>
                    {kb.name} ({kb.id})
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm text-gray-700 dark:text-gray-300" data-name="chunk-inspector-doc">
              <span className="font-medium text-gray-900 dark:text-white">Document</span>
              <select
                value={selectedDoc}
                onChange={(event) => setSelectedDoc(event.target.value)}
                disabled={!selectedKb || loadingDocs}
                className="mt-2 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 disabled:opacity-60"
              >
                <option value="">All documents</option>
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.filename} ({doc.id})
                  </option>
                ))}
              </select>
              {loadingDocs && (
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">Loading documents...</div>
              )}
              {docError && (
                <div className="mt-1 text-xs text-red-600 dark:text-red-400">{docError}</div>
              )}
            </label>

            <label className="block text-sm text-gray-700 dark:text-gray-300" data-name="chunk-inspector-limit">
              <span className="font-medium text-gray-900 dark:text-white">Limit</span>
              <input
                type="number"
                min={1}
                max={2000}
                value={limit}
                onChange={(event) => setLimit(Number(event.target.value))}
                className="mt-2 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
              />
              <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">Max 2000</div>
            </label>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3" data-name="chunk-inspector-actions">
            <div className="text-xs text-gray-500 dark:text-gray-400">{chunkSummary}</div>
            <button
              type="button"
              onClick={fetchChunks}
              disabled={!selectedKb || kbHook.loading || loadingChunks}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {loadingChunks ? 'Fetching...' : 'Fetch chunks'}
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4" data-name="chunk-inspector-status">
          <div className="text-sm font-medium text-gray-900 dark:text-white">Status</div>
          <div className="mt-2 space-y-2 text-sm text-gray-600 dark:text-gray-300">
            <div>Knowledge bases: {kbHook.loading ? 'Loading...' : kbHook.knowledgeBases.length}</div>
            <div>Documents: {loadingDocs ? 'Loading...' : documents.length}</div>
            <div>Chunks: {loadingChunks ? 'Loading...' : chunks.length}</div>
          </div>
          {kbHook.error && (
            <div className="mt-3 text-xs text-red-600 dark:text-red-400">{kbHook.error}</div>
          )}
          {chunkError && (
            <div className="mt-3 text-xs text-red-600 dark:text-red-400">{chunkError}</div>
          )}
        </div>
      </div>

      <div className="space-y-4" data-name="chunk-inspector-results">
        {chunks.length === 0 && !loadingChunks && (
          <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-700 p-6 text-center text-sm text-gray-500 dark:text-gray-400">
            No chunks loaded. Fetch to inspect semantic splitting output.
          </div>
        )}

        {chunks.map((chunk) => (
          <div
            key={chunk.id}
            className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4"
            data-name="chunk-card"
          >
            <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
              <span>Doc: {chunk.doc_id || 'n/a'}</span>
              <span>•</span>
              <span>Index: {chunk.chunk_index}</span>
              <span>•</span>
              <span>ID: {chunk.id}</span>
              {chunk.filename && (
                <>
                  <span>•</span>
                  <span>File: {chunk.filename}</span>
                </>
              )}
            </div>
            <div className="mt-3 whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200">
              {chunk.content}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
