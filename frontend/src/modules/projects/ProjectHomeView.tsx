import React, { useCallback, useMemo } from 'react';
import {
  ArrowLeftIcon,
  ArrowPathIcon,
  CommandLineIcon,
  DocumentTextIcon,
  FolderOpenIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { useNavigate, useOutletContext } from 'react-router-dom';
import {
  addProjectWorkspaceItem,
  type ProjectWorkspaceRecentItem,
} from '../../services/api';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import type { ProjectWorkspaceOutletContext } from './workspace';
import { getProjectWorkspacePath } from './workspace';
import { useProjectHomeSummary } from './hooks/useProjectHomeSummary';
import { useProjectWorkspaceState } from './hooks/useProjectWorkspaceState';

const formatDateTime = (value: string | null | undefined): string => {
  if (!value) {
    return '--';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
};

const getRunStatusClass = (status: string | undefined): string => {
  if (status === 'succeeded') {
    return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300';
  }
  if (status === 'running' || status === 'queued') {
    return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300';
  }
  return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300';
};

export const ProjectHomeView: React.FC = () => {
  const { t } = useTranslation('projects');
  const navigate = useNavigate();
  const { projectId, currentProject, onManageClick, onCloseProject } = useOutletContext<ProjectWorkspaceOutletContext>();
  const setChatSidebarOpen = useProjectWorkspaceStore((state) => state.setChatSidebarOpen);
  const setProjectSession = useProjectWorkspaceStore((state) => state.setProjectSession);
  const setCurrentFile = useProjectWorkspaceStore((state) => state.setCurrentFile);
  const summary = useProjectHomeSummary(projectId);
  const workspaceState = useProjectWorkspaceState(projectId);

  const openPath = useCallback((path: string) => {
    navigate(path);
  }, [navigate]);

  const openWorkspaceItem = useCallback((item: ProjectWorkspaceRecentItem) => {
    void addProjectWorkspaceItem(projectId, {
      type: item.type,
      id: item.id,
      title: item.title,
      path: item.path || undefined,
      meta: item.meta,
    }).catch((error) => {
      console.error('Failed to persist project workspace item:', error);
    });

    if (item.type === 'file') {
      const targetPath = item.path || item.id;
      setCurrentFile(projectId, targetPath);
      navigate(getProjectWorkspacePath(projectId, 'files'));
      return;
    }

    if (item.type === 'session') {
      setProjectSession(projectId, item.id);
      setChatSidebarOpen(true);
      navigate(getProjectWorkspacePath(projectId, 'files'));
      return;
    }

    navigate(getProjectWorkspacePath(projectId, 'workflows'));
  }, [navigate, projectId, setChatSidebarOpen, setCurrentFile, setProjectSession]);

  const currentWork = workspaceState.workspaceState?.recent_items?.[0] || null;
  const recentItems = workspaceState.workspaceState?.recent_items || [];

  const currentWorkDescription = useMemo(() => {
    if (!currentWork) {
      return t('projectHome.emptyCurrentWorkDescription');
    }

    if (currentWork.type === 'file') {
      return currentWork.path || t('projectHome.lastFileHint');
    }

    if (currentWork.type === 'session') {
      return t('projectHome.currentWorkSessionHint', {
        updatedAt: formatDateTime(currentWork.updated_at),
      });
    }

    const status = typeof currentWork.meta?.status === 'string' ? currentWork.meta.status : undefined;
    const artifactPath = typeof currentWork.meta?.artifact_path === 'string' ? currentWork.meta.artifact_path : undefined;
    if (artifactPath) {
      return artifactPath;
    }
    return t('projectHome.currentWorkRunHint', {
      status: status || 'unknown',
      updatedAt: formatDateTime(currentWork.updated_at),
    });
  }, [currentWork, t]);

  const currentWorkLabel = currentWork
    ? currentWork.type === 'file'
      ? t('projectHome.continueEditing')
      : currentWork.type === 'session'
        ? t('projectHome.continueConversation')
        : t('projectHome.viewWorkflowRun')
    : t('projectHome.emptyOpenFiles');

  const handleCurrentWorkOpen = () => {
    if (currentWork) {
      openWorkspaceItem(currentWork);
      return;
    }
    openPath(getProjectWorkspacePath(projectId, 'files'));
  };

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

  return (
    <div data-name="project-home-view" className="flex h-full min-h-0 w-full flex-1 flex-col overflow-auto bg-gray-50 px-4 py-4 dark:bg-gray-950">
      <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_320px]">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-gray-900 dark:text-white">
              {currentProject.name}
            </h1>
            {currentProject.description?.trim() && (
              <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-600 dark:text-gray-300">
                {currentProject.description}
              </p>
            )}

            <div className="mt-4 rounded-2xl bg-gray-50 px-4 py-3 text-xs text-gray-600 dark:bg-gray-950 dark:text-gray-300">
              {currentProject.root_path}
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleCurrentWorkOpen}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700"
                data-name="project-home-primary-cta"
              >
                <DocumentTextIcon className="h-4 w-4" />
                {currentWorkLabel}
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
                {t('projectHome.lastSession')}: {summary.recentSessionId || t('projectHome.noRecentSession')}
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
          <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900" data-name="project-home-current-work">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
              <DocumentTextIcon className="h-4 w-4" />
              {t('projectHome.currentWorkTitle')}
            </div>
            {workspaceState.loading && !workspaceState.workspaceState ? (
              <div className="mt-4 text-sm text-gray-600 dark:text-gray-300">{t('projectHome.workspaceStateLoading')}</div>
            ) : workspaceState.error && !workspaceState.workspaceState ? (
              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
                {workspaceState.error}
              </div>
            ) : (
              <div className="mt-4 rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                <div className="inline-flex rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-500 dark:bg-gray-900 dark:text-gray-400">
                  {t(`projectHome.currentWorkKind.${currentWork?.type || 'empty'}`)}
                </div>
                <div className="mt-3 text-lg font-semibold text-gray-900 dark:text-white">
                  {currentWork?.title || t('projectHome.emptyCurrentWorkTitle')}
                </div>
                <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">{currentWorkDescription}</div>
                <button
                  type="button"
                  onClick={handleCurrentWorkOpen}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700"
                  data-name="project-home-current-work-cta"
                >
                  {currentWorkLabel}
                </button>
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900" data-name="project-home-recent-activity">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
                  <DocumentTextIcon className="h-4 w-4" />
                  {t('projectHome.recentActivityTitle')}
                </div>
              </div>
              <button
                type="button"
                onClick={() => void workspaceState.refresh()}
                className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-gray-300 bg-white text-gray-600 transition hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
                data-name="project-home-refresh-workspace-state"
                title={t('workspace.workflows.refreshRuns')}
              >
                <ArrowPathIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 space-y-3">
              {workspaceState.loading && !workspaceState.workspaceState ? (
                <div className="text-sm text-gray-600 dark:text-gray-300">{t('projectHome.workspaceStateLoading')}</div>
              ) : workspaceState.error && !workspaceState.workspaceState ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
                  {workspaceState.error}
                </div>
              ) : recentItems.length === 0 ? (
                <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-sm text-gray-600 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-300">
                  {t('projectHome.workspaceStateEmpty')}
                </div>
              ) : (
                recentItems.slice(0, 8).map((item) => {
                  const runStatus = typeof item.meta?.status === 'string' ? item.meta.status : undefined;
                  const runArtifact = typeof item.meta?.artifact_path === 'string' ? item.meta.artifact_path : undefined;
                  return (
                    <button
                      key={`${item.type}:${item.id}`}
                      type="button"
                      onClick={() => openWorkspaceItem(item)}
                      className="w-full rounded-2xl border border-gray-200 bg-gray-50 p-4 text-left transition hover:border-blue-300 hover:bg-blue-50 dark:border-gray-800 dark:bg-gray-950 dark:hover:border-blue-700 dark:hover:bg-blue-950/20"
                      data-name="project-home-recent-item"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-gray-500 dark:bg-gray-900 dark:text-gray-400">
                              {t(`projectHome.currentWorkKind.${item.type}`)}
                            </span>
                            {item.type === 'run' && runStatus && (
                              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${getRunStatusClass(runStatus)}`}>
                                {runStatus}
                              </span>
                            )}
                          </div>
                          <div className="mt-2 truncate text-sm font-semibold text-gray-900 dark:text-gray-100">
                            {item.title}
                          </div>
                          <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                            {item.type === 'file'
                              ? (item.path || item.id)
                              : item.type === 'session'
                                ? formatDateTime(item.updated_at)
                                : (runArtifact || formatDateTime(item.updated_at))}
                          </div>
                        </div>
                        <span className="text-xs font-medium text-blue-700 dark:text-blue-300">
                          {item.type === 'file'
                            ? t('projectHome.continueEditing')
                            : item.type === 'session'
                              ? t('projectHome.continueConversation')
                              : t('projectHome.viewWorkflowRun')}
                        </span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </section>
        </div>

        <div className="space-y-4">
          <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
              <SparklesIcon className="h-4 w-4" />
              {t('projectHome.aiActionsTitle')}
            </div>
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
