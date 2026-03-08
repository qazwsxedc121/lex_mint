import React, { useEffect, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { searchProjectText } from '../../services/api';
import type { ProjectTextSearchMatch } from '../../services/api';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import type { ProjectWorkspaceOutletContext } from './workspace';
import { getProjectWorkspacePath } from './workspace';
import { buildSearchAgentContextItem } from './agentContext';

export const ProjectSearchView: React.FC = () => {
  const { t } = useTranslation('projects');
  const navigate = useNavigate();
  const { projectId, currentProject } = useOutletContext<ProjectWorkspaceOutletContext>();
  const { setCurrentFile, addAgentContextItems } = useProjectWorkspaceStore();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<ProjectTextSearchMatch[]>([]);
  const [truncated, setTruncated] = useState(false);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setLoading(false);
      setError(null);
      setResults([]);
      setTruncated(false);
      return;
    }

    setLoading(true);
    setError(null);
    const timeoutId = window.setTimeout(async () => {
      try {
        const payload = await searchProjectText(projectId, trimmed, {
          maxResults: 80,
          contextLines: 1,
          maxCharsPerLine: 240,
        });
        setResults(payload.results || []);
        setTruncated(Boolean(payload.truncated));
      } catch (err: any) {
        const message = err?.response?.data?.detail || err?.message || t('fileTree.textSearch.error');
        setError(String(message));
        setResults([]);
        setTruncated(false);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => window.clearTimeout(timeoutId);
  }, [projectId, query, t]);

  const handleOpenResult = (item: ProjectTextSearchMatch) => {
    setCurrentFile(projectId, item.file_path);
    navigate(getProjectWorkspacePath(projectId, 'files'));
    window.setTimeout(() => {
      window.dispatchEvent(new CustomEvent('project-open-line', {
        detail: {
          filePath: item.file_path,
          line: item.line_number,
        },
      }));
    }, 50);
  };

  const handleSendResultToAgent = (item: ProjectTextSearchMatch) => {
    addAgentContextItems(projectId, [buildSearchAgentContextItem(item, query.trim())]);
    navigate(getProjectWorkspacePath(projectId, 'agent'));
  };

  return (
    <div data-name="project-search-view" className="flex h-full min-h-0 flex-col overflow-hidden bg-gray-50 dark:bg-gray-950">
      <div className="border-b border-gray-200 bg-white px-4 py-4 dark:border-gray-800 dark:bg-gray-900">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-blue-50 p-2 text-blue-700 dark:bg-blue-900/30 dark:text-blue-200">
            <MagnifyingGlassIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{t('workspace.search.title')}</h2>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
              {t('workspace.search.description', { projectName: currentProject?.name || 'project' })}
            </p>
          </div>
        </div>

        <div className="mt-4">
          <label className="relative block" data-name="project-search-input-wrap">
            <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              data-name="project-search-input"
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('workspace.search.placeholder')}
              className="w-full rounded-xl border border-gray-300 bg-white py-2.5 pl-10 pr-4 text-sm text-gray-900 shadow-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100 dark:focus:border-blue-400 dark:focus:ring-blue-900/40"
            />
          </label>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {!query.trim() ? (
          <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center dark:border-gray-700 dark:bg-gray-900">
            <p className="text-sm text-gray-600 dark:text-gray-300">{t('workspace.search.emptyState')}</p>
          </div>
        ) : loading ? (
          <div className="rounded-2xl border border-gray-200 bg-white p-6 text-sm text-gray-600 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-300">
            {t('fileTree.textSearch.loading')}
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300">
            {error}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3 px-1">
              <div className="text-sm text-gray-600 dark:text-gray-300">
                {results.length > 0
                  ? t('fileTree.textSearch.resultCount', { count: results.length })
                  : t('fileTree.textSearch.noResults')}
              </div>
              {truncated && (
                <div className="text-xs text-amber-700 dark:text-amber-300">{t('fileTree.textSearch.truncated')}</div>
              )}
            </div>

            {results.map((item, index) => (
              <div
                key={`${item.file_path}:${item.line_number}:${index}`}
                data-name="project-search-result-item"
                className="rounded-2xl border border-gray-200 bg-white p-4 transition hover:border-blue-300 hover:bg-blue-50/40 dark:border-gray-800 dark:bg-gray-900 dark:hover:border-blue-700 dark:hover:bg-blue-950/20"
              >
                <div className="flex items-start justify-between gap-3">
                  <button
                    type="button"
                    onClick={() => handleOpenResult(item)}
                    className="min-w-0 flex-1 text-left"
                  >
                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {item.file_path}
                    </div>
                    <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      {t('workspace.search.lineLabel', { line: item.line_number })}
                    </div>
                    <div className="mt-2 break-words text-sm text-gray-700 dark:text-gray-300">
                      {item.line_text}
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleSendResultToAgent(item)}
                    className="shrink-0 rounded-lg border border-gray-300 px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                    data-name="project-search-send-to-agent"
                  >
                    {t('workspace.agent.sendToAgent')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
