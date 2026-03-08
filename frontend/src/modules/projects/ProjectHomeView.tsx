import React from 'react';
import {
  ArrowLeftIcon,
  ChatBubbleLeftRightIcon,
  CommandLineIcon,
  DocumentTextIcon,
  FolderOpenIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import type { ProjectWorkspaceOutletContext } from './workspace';
import { getProjectWorkspacePath } from './workspace';
import { useProjectHomeSummary } from './hooks/useProjectHomeSummary';

const formatSessionLabel = (sessionId: string | null): string => {
  if (!sessionId) {
    return '--';
  }

  return sessionId.length > 16 ? `${sessionId.slice(0, 8)}...${sessionId.slice(-4)}` : sessionId;
};

export const ProjectHomeView: React.FC = () => {
  const { t } = useTranslation('projects');
  const navigate = useNavigate();
  const { projectId, currentProject, onManageClick, onCloseProject } = useOutletContext<ProjectWorkspaceOutletContext>();
  const setChatSidebarOpen = useProjectWorkspaceStore((state) => state.setChatSidebarOpen);
  const summary = useProjectHomeSummary(projectId);

  if (!currentProject) {
    return (
      <div className="flex flex-1 items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400">{t('explorer.invalidId')}</p>
          <button
            type="button"
            onClick={onCloseProject}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {t('projectHome.backToDashboard')}
          </button>
        </div>
      </div>
    );
  }

  const openRecentConversation = () => {
    setChatSidebarOpen(true);
    navigate(getProjectWorkspacePath(projectId, 'files'));
  };

  const openPath = (path: string) => navigate(path);

  return (
    <div data-name="project-home-view" className="flex h-full min-h-0 w-full flex-1 flex-col overflow-auto bg-gray-50 px-4 py-4 dark:bg-gray-950">
      <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_320px]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
              <SparklesIcon className="h-4 w-4" />
              {t('projectHome.eyebrow')}
            </div>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-gray-900 dark:text-white">
              {currentProject.name}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-600 dark:text-gray-300">
              {currentProject.description?.trim() || t('projectHome.descriptionFallback')}
            </p>

            <div className="mt-4 rounded-2xl bg-gray-50 px-4 py-3 text-xs text-gray-600 dark:bg-gray-950 dark:text-gray-300">
              {currentProject.root_path}
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => openPath(summary.continueEditingPath)}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700"
                data-name="project-home-continue-editing"
              >
                <DocumentTextIcon className="h-4 w-4" />
                {t('projectHome.continueEditing')}
              </button>
              <button
                type="button"
                onClick={() => openPath(getProjectWorkspacePath(projectId, 'search'))}
                className="inline-flex items-center gap-2 rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 transition hover:border-gray-400 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:border-gray-600 dark:hover:bg-gray-800"
                data-name="project-home-open-search"
              >
                <MagnifyingGlassIcon className="h-4 w-4" />
                {t('projectHome.openSearch')}
              </button>
              <button
                type="button"
                onClick={() => openPath(getProjectWorkspacePath(projectId, 'workflows'))}
                className="inline-flex items-center gap-2 rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 transition hover:border-gray-400 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:border-gray-600 dark:hover:bg-gray-800"
                data-name="project-home-open-workflows"
              >
                <CommandLineIcon className="h-4 w-4" />
                {t('projectHome.openWorkflows')}
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-5 dark:border-gray-800 dark:bg-gray-950/60">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
              <FolderOpenIcon className="h-4 w-4" />
              {t('projectHome.statusTitle')}
            </div>
            <div className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-300">
              <div className="rounded-xl bg-white px-3 py-2 dark:bg-gray-900">
                {t('projectHome.lastTab')}: {t(`workspace.tabs.${summary.recentTab}`)}
              </div>
              <div className="rounded-xl bg-white px-3 py-2 dark:bg-gray-900">
                {t('projectHome.lastFile')}: {summary.recentFileName || t('projectHome.noRecentFile')}
              </div>
              <div className="rounded-xl bg-white px-3 py-2 dark:bg-gray-900">
                {t('projectHome.lastSession')}: {summary.recentSessionId ? formatSessionLabel(summary.recentSessionId) : t('projectHome.noRecentSession')}
              </div>
              <div className="rounded-xl bg-white px-3 py-2 dark:bg-gray-900">
                {t('projectHome.sidebarState')}: {summary.chatSidebarOpen ? t('projectHome.sidebarOpen') : t('projectHome.sidebarClosed')}
              </div>
              <div className="rounded-xl bg-white px-3 py-2 dark:bg-gray-900">
                {t('projectHome.fileTreeState')}: {summary.fileTreeOpen ? t('projectHome.fileTreeOpen') : t('projectHome.fileTreeClosed')}
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onManageClick}
                className="rounded-xl bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-800 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-100"
                data-name="project-home-manage-project"
              >
                {t('welcome.manageProjects')}
              </button>
              <button
                type="button"
                onClick={onCloseProject}
                className="inline-flex items-center gap-2 rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:border-gray-600 dark:hover:bg-gray-800"
                data-name="project-home-back-dashboard"
              >
                <ArrowLeftIcon className="h-4 w-4" />
                {t('projectHome.backToDashboard')}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
              <DocumentTextIcon className="h-4 w-4" />
              {t('projectHome.continueTitle')}
            </div>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{t('projectHome.continueDescription')}</p>

            {summary.hasWorkContext ? (
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <button
                  type="button"
                  onClick={() => openPath(summary.continueEditingPath)}
                  className="rounded-2xl border border-gray-200 bg-gray-50 p-4 text-left transition hover:border-blue-300 hover:bg-blue-50 dark:border-gray-800 dark:bg-gray-950 dark:hover:border-blue-700 dark:hover:bg-blue-950/20"
                  data-name="project-home-recent-file-card"
                >
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-gray-400">
                    {t('projectHome.lastFile')}
                  </div>
                  <div className="mt-2 text-base font-semibold text-gray-900 dark:text-white">
                    {summary.recentFileName || t('projectHome.noRecentFile')}
                  </div>
                  <div className="mt-2 line-clamp-2 text-sm text-gray-600 dark:text-gray-300">
                    {summary.recentFilePath || t('projectHome.lastFileHint')}
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => openPath(summary.recentTabPath)}
                  className="rounded-2xl border border-gray-200 bg-gray-50 p-4 text-left transition hover:border-blue-300 hover:bg-blue-50 dark:border-gray-800 dark:bg-gray-950 dark:hover:border-blue-700 dark:hover:bg-blue-950/20"
                  data-name="project-home-last-tab-card"
                >
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-gray-400">
                    {t('projectHome.lastTab')}
                  </div>
                  <div className="mt-2 text-base font-semibold text-gray-900 dark:text-white">
                    {t(`workspace.tabs.${summary.recentTab}`)}
                  </div>
                  <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                    {t('projectHome.lastTabHint')}
                  </div>
                </button>

                <button
                  type="button"
                  onClick={openRecentConversation}
                  className="rounded-2xl border border-gray-200 bg-gray-50 p-4 text-left transition hover:border-blue-300 hover:bg-blue-50 dark:border-gray-800 dark:bg-gray-950 dark:hover:border-blue-700 dark:hover:bg-blue-950/20"
                  data-name="project-home-session-card"
                >
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-gray-400">
                    {t('projectHome.lastSession')}
                  </div>
                  <div className="mt-2 text-base font-semibold text-gray-900 dark:text-white">
                    {summary.recentSessionId ? t('projectHome.continueConversation') : t('projectHome.noRecentSession')}
                  </div>
                  <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                    {summary.recentSessionId ? formatSessionLabel(summary.recentSessionId) : t('projectHome.lastSessionHint')}
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => openPath(getProjectWorkspacePath(projectId, 'workflows'))}
                  className="rounded-2xl border border-gray-200 bg-gray-50 p-4 text-left transition hover:border-blue-300 hover:bg-blue-50 dark:border-gray-800 dark:bg-gray-950 dark:hover:border-blue-700 dark:hover:bg-blue-950/20"
                  data-name="project-home-workflow-card"
                >
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-gray-400">
                    {t('workspace.tabs.workflows')}
                  </div>
                  <div className="mt-2 text-base font-semibold text-gray-900 dark:text-white">
                    {t('projectHome.runWorkflow')}
                  </div>
                  <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                    {t('projectHome.workflowHint')}
                  </div>
                </button>
              </div>
            ) : (
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <button
                  type="button"
                  onClick={() => openPath(getProjectWorkspacePath(projectId, 'files'))}
                  className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-4 text-left transition hover:border-blue-300 hover:bg-blue-50 dark:border-gray-700 dark:bg-gray-950 dark:hover:border-blue-700 dark:hover:bg-blue-950/20"
                  data-name="project-home-empty-open-files"
                >
                  <div className="text-sm font-semibold text-gray-900 dark:text-white">{t('projectHome.emptyOpenFiles')}</div>
                  <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">{t('projectHome.emptyOpenFilesHint')}</div>
                </button>
                <button
                  type="button"
                  onClick={() => openPath(getProjectWorkspacePath(projectId, 'search'))}
                  className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-4 text-left transition hover:border-blue-300 hover:bg-blue-50 dark:border-gray-700 dark:bg-gray-950 dark:hover:border-blue-700 dark:hover:bg-blue-950/20"
                  data-name="project-home-empty-search"
                >
                  <div className="text-sm font-semibold text-gray-900 dark:text-white">{t('projectHome.emptySearch')}</div>
                  <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">{t('projectHome.emptySearchHint')}</div>
                </button>
                <button
                  type="button"
                  onClick={() => openPath(getProjectWorkspacePath(projectId, 'workflows'))}
                  className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-4 text-left transition hover:border-blue-300 hover:bg-blue-50 dark:border-gray-700 dark:bg-gray-950 dark:hover:border-blue-700 dark:hover:bg-blue-950/20"
                  data-name="project-home-empty-workflows"
                >
                  <div className="text-sm font-semibold text-gray-900 dark:text-white">{t('projectHome.emptyWorkflow')}</div>
                  <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">{t('projectHome.emptyWorkflowHint')}</div>
                </button>
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
              <ChatBubbleLeftRightIcon className="h-4 w-4" />
              {t('projectHome.resourcesTitle')}
            </div>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{t('projectHome.resourcesDescription')}</p>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <button
                type="button"
                onClick={() => openPath(getProjectWorkspacePath(projectId, 'files'))}
                className="rounded-2xl bg-gray-50 px-4 py-4 text-left text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
                data-name="project-home-resource-files"
              >
                {t('workspace.tabs.files')}
              </button>
              <button
                type="button"
                onClick={() => openPath(getProjectWorkspacePath(projectId, 'search'))}
                className="rounded-2xl bg-gray-50 px-4 py-4 text-left text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
                data-name="project-home-resource-search"
              >
                {t('workspace.tabs.search')}
              </button>
              <button
                type="button"
                onClick={() => openPath(getProjectWorkspacePath(projectId, 'workflows'))}
                className="rounded-2xl bg-gray-50 px-4 py-4 text-left text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
                data-name="project-home-resource-workflows"
              >
                {t('workspace.tabs.workflows')}
              </button>
            </div>
          </section>
        </div>

        <div className="space-y-4">
          <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
              <SparklesIcon className="h-4 w-4" />
              {t('projectHome.aiActionsTitle')}
            </div>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{t('projectHome.aiActionsDescription')}</p>
            <div className="mt-4 space-y-2">
              <button
                type="button"
                onClick={() => openPath(getProjectWorkspacePath(projectId, 'files'))}
                className="flex w-full items-center gap-3 rounded-xl bg-gray-50 px-4 py-3 text-left text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
                data-name="project-home-ai-files"
              >
                <DocumentTextIcon className="h-4 w-4 flex-none" />
                {t('projectHome.aiFilesAction')}
              </button>
              <button
                type="button"
                onClick={() => openPath(getProjectWorkspacePath(projectId, 'search'))}
                className="flex w-full items-center gap-3 rounded-xl bg-gray-50 px-4 py-3 text-left text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
                data-name="project-home-ai-search"
              >
                <MagnifyingGlassIcon className="h-4 w-4 flex-none" />
                {t('projectHome.aiSearchAction')}
              </button>
              <button
                type="button"
                onClick={() => openPath(getProjectWorkspacePath(projectId, 'workflows'))}
                className="flex w-full items-center gap-3 rounded-xl bg-gray-50 px-4 py-3 text-left text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
                data-name="project-home-ai-workflow"
              >
                <CommandLineIcon className="h-4 w-4 flex-none" />
                {t('projectHome.aiWorkflowAction')}
              </button>
            </div>
          </section>
        </div>
      </section>
    </div>
  );
};
