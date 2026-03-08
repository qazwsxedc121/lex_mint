import React, { useCallback, useEffect, useState } from 'react';
import {
  ArrowPathIcon,
  ChatBubbleLeftRightIcon,
  Cog6ToothIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { useOutletContext } from 'react-router-dom';
import { deleteSession, listSessions } from '../../services/api';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import type { ProjectWorkspaceOutletContext } from './workspace';

type FeedbackState =
  | { type: 'success'; message: string }
  | { type: 'error'; message: string }
  | null;

export const ProjectSettingsView: React.FC = () => {
  const { t } = useTranslation('projects');
  const { projectId, currentProject } = useOutletContext<ProjectWorkspaceOutletContext>();
  const setProjectSession = useProjectWorkspaceStore((state) => state.setProjectSession);
  const setAgentSession = useProjectWorkspaceStore((state) => state.setAgentSession);
  const clearAgentContextItems = useProjectWorkspaceStore((state) => state.clearAgentContextItems);
  const [sessionCount, setSessionCount] = useState<number>(0);
  const [loadingCount, setLoadingCount] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const loadSessionCount = useCallback(async () => {
    setLoadingCount(true);
    setLoadError(null);
    try {
      const sessions = await listSessions('project', projectId);
      setSessionCount(sessions.length);
    } catch (error) {
      console.error('Failed to load project session count:', error);
      setLoadError(t('workspace.settings.chatHistoryCountFailed'));
    } finally {
      setLoadingCount(false);
    }
  }, [projectId, t]);

  useEffect(() => {
    void loadSessionCount();
  }, [loadSessionCount]);

  const handleDeleteAllConversations = useCallback(async () => {
    const confirmed = window.confirm(
      t('workspace.settings.deleteAllConversationsConfirm', {
        count: sessionCount,
        projectName: currentProject?.name || projectId,
      })
    );

    if (!confirmed) {
      return;
    }

    setDeleting(true);
    setFeedback(null);

    try {
      const sessions = await listSessions('project', projectId);
      for (const session of sessions) {
        await deleteSession(session.session_id, 'project', projectId);
      }

      setProjectSession(projectId, null);
      setAgentSession(projectId, null);
      clearAgentContextItems(projectId);
      setSessionCount(0);
      setFeedback({
        type: 'success',
        message: t('workspace.settings.deleteAllConversationsSuccess', { count: sessions.length }),
      });
      await loadSessionCount();
    } catch (error) {
      console.error('Failed to delete project conversations:', error);
      setFeedback({
        type: 'error',
        message: t('workspace.settings.deleteAllConversationsFailed'),
      });
    } finally {
      setDeleting(false);
    }
  }, [clearAgentContextItems, currentProject?.name, loadSessionCount, projectId, sessionCount, setAgentSession, setProjectSession, t]);

  return (
    <div
      data-name="project-settings-view"
      className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden bg-gray-50 px-4 py-4 dark:bg-gray-950"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-200 bg-white px-4 py-3 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="flex min-w-0 items-start gap-3">
          <div className="rounded-xl bg-gray-100 p-2 text-gray-700 dark:bg-gray-800 dark:text-gray-200">
            <Cog6ToothIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{t('workspace.settings.title')}</h2>
            <p className="mt-0.5 text-sm text-gray-600 dark:text-gray-300">
              {t('workspace.settings.description', { projectName: currentProject?.name || projectId })}
            </p>
          </div>
        </div>
        {currentProject && (
          <div className="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-medium text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200">
            {currentProject.name}
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <section
          data-name="project-settings-chat-history"
          className="max-w-4xl rounded-2xl border border-red-200 bg-white p-5 shadow-sm dark:border-red-900/50 dark:bg-gray-900"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-sm font-semibold text-red-700 dark:text-red-300">
                <ChatBubbleLeftRightIcon className="h-4 w-4" />
                {t('workspace.settings.chatHistoryTitle')}
              </div>
              <p className="mt-2 max-w-2xl text-sm text-gray-600 dark:text-gray-300">
                {t('workspace.settings.chatHistoryDescription')}
              </p>
            </div>

            <button
              type="button"
              onClick={() => void loadSessionCount()}
              disabled={loadingCount || deleting}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
              data-name="project-settings-refresh-count"
            >
              <ArrowPathIcon className={`h-4 w-4 ${loadingCount ? 'animate-spin' : ''}`} />
              {t('workspace.settings.refresh')}
            </button>
          </div>

          <div className="mt-5 rounded-2xl border border-red-100 bg-red-50/70 p-4 dark:border-red-900/40 dark:bg-red-950/20">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-red-700 dark:text-red-300">
                  {t('workspace.settings.dangerZone')}
                </div>
                <div className="mt-2 text-sm text-gray-700 dark:text-gray-200">
                  {loadingCount
                    ? t('chat.loading')
                    : loadError || t('workspace.settings.chatHistoryCount', { count: sessionCount })}
                </div>
              </div>

              <button
                type="button"
                onClick={() => void handleDeleteAllConversations()}
                disabled={deleting || loadingCount || sessionCount === 0}
                className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-400 disabled:text-red-100 dark:disabled:bg-red-900/50"
                data-name="project-settings-delete-all-conversations"
              >
                <TrashIcon className="h-4 w-4" />
                {deleting
                  ? t('workspace.settings.deleteAllConversationsRunning')
                  : t('workspace.settings.deleteAllConversations')}
              </button>
            </div>

            {feedback && (
              <div
                className={`mt-4 rounded-xl border px-3 py-2 text-sm ${
                  feedback.type === 'success'
                    ? 'border-green-200 bg-green-50 text-green-700 dark:border-green-900/50 dark:bg-green-950/20 dark:text-green-300'
                    : 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300'
                }`}
                data-name="project-settings-feedback"
              >
                {feedback.message}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};
