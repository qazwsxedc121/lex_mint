import React from 'react';
import {
  ArrowRightIcon,
  ClockIcon,
  FolderIcon,
  FolderOpenIcon,
  PlusIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import type { ProjectsOutletContext } from './workspace';
import { useProjectsDashboardSummary } from './hooks/useProjectsDashboardSummary';

const formatSessionLabel = (sessionId: string | null): string => {
  if (!sessionId) {
    return '--';
  }

  return sessionId.length > 16 ? `${sessionId.slice(0, 8)}...${sessionId.slice(-4)}` : sessionId;
};

export const ProjectsDashboardView: React.FC = () => {
  const { t } = useTranslation('projects');
  const navigate = useNavigate();
  const setCurrentProject = useProjectWorkspaceStore((state) => state.setCurrentProject);
  const { projects, projectsLoading = false, onManageClick, onAddProjectClick } = useOutletContext<ProjectsOutletContext>();
  const summary = useProjectsDashboardSummary(projects);

  const handleOpenProject = (projectId: string, path: string) => {
    setCurrentProject(projectId);
    navigate(path);
  };

  const recentProject = summary.recentProject;
  const projectItems = recentProject ? [recentProject, ...summary.otherProjects] : summary.otherProjects;

  return (
    <div data-name="projects-dashboard-view" className="flex h-full min-h-0 w-full flex-1 flex-col overflow-auto bg-gray-50 px-4 py-4 dark:bg-gray-950">
      <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_320px]">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-gray-900 dark:text-white">
              {t('dashboard.title')}
            </h1>
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => {
                  if (recentProject) {
                    handleOpenProject(recentProject.project.id, recentProject.openPath);
                    return;
                  }
                  onAddProjectClick();
                }}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700"
                data-name="projects-dashboard-primary-cta"
              >
                <ArrowRightIcon className="h-4 w-4" />
                {recentProject ? t('dashboard.continueRecent') : t('dashboard.createFirstProject')}
              </button>
              <button
                type="button"
                onClick={onAddProjectClick}
                className="inline-flex items-center gap-2 rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 transition hover:border-gray-400 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:border-gray-600 dark:hover:bg-gray-800"
                data-name="projects-dashboard-add-project"
              >
                <PlusIcon className="h-4 w-4" />
                {t('welcome.addProject')}
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950/60">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
              <ClockIcon className="h-4 w-4" />
              {t('dashboard.recentProjectTitle')}
            </div>

            {recentProject ? (
              <div className="mt-4 space-y-4">
                <div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">{recentProject.project.name}</div>
                  {recentProject.project.description?.trim() && (
                    <div className="mt-1 line-clamp-2 text-sm text-gray-600 dark:text-gray-300">
                      {recentProject.project.description}
                    </div>
                  )}
                </div>

                <div className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
                  <div className="rounded-xl bg-white px-3 py-2 dark:bg-gray-900">
                    {t('dashboard.lastTab')}: {t(`workspace.tabs.${recentProject.lastTab}`)}
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2 dark:bg-gray-900">
                    {t('dashboard.lastFile')}: {recentProject.lastFileName || t('dashboard.noRecentFile')}
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2 dark:bg-gray-900">
                    {t('dashboard.lastSession')}: {recentProject.lastSessionId ? formatSessionLabel(recentProject.lastSessionId) : t('dashboard.noRecentSession')}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleOpenProject(recentProject.project.id, recentProject.openPath)}
                  className="inline-flex items-center gap-2 rounded-xl bg-gray-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gray-800 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-100"
                  data-name="projects-dashboard-open-recent"
                >
                  <FolderOpenIcon className="h-4 w-4" />
                  {t('dashboard.openRecentProject')}
                </button>
              </div>
            ) : (
              <div className="mt-4 rounded-2xl border border-dashed border-gray-300 bg-white px-4 py-6 text-sm text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300">
                {t('dashboard.noRecentProject')}
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('dashboard.projectsTitle')}</h2>
            </div>
            <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-300">
              {summary.totalProjects}
            </span>
          </div>

          <div className="mt-4">
            {projectsLoading ? (
              <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-300">
                {t('explorer.loading')}
              </div>
            ) : summary.totalProjects === 0 ? (
              <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 px-4 py-8 text-center text-sm text-gray-600 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-300">
                {t('dashboard.noProjects')}
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {projectItems.map((item) => (
                  <button
                    key={item.project.id}
                    type="button"
                    onClick={() => handleOpenProject(item.project.id, item.openPath)}
                    className={`rounded-2xl border p-4 text-left transition ${
                      item.isCurrent
                        ? 'border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-950/30'
                        : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50 dark:border-gray-800 dark:bg-gray-900 dark:hover:border-gray-700 dark:hover:bg-gray-950/40'
                    }`}
                    data-name="projects-dashboard-project-item"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-gray-900 dark:text-gray-100">{item.project.name}</div>
                        {item.project.description?.trim() && (
                          <div className="mt-1 line-clamp-2 text-sm text-gray-600 dark:text-gray-300">
                            {item.project.description}
                          </div>
                        )}
                      </div>
                      {item.isCurrent && (
                        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-200">
                          {t('workspace.project.currentBadge')}
                        </span>
                      )}
                    </div>

                    <div className="mt-4 space-y-2 text-xs text-gray-500 dark:text-gray-400">
                      <div className="truncate">{item.project.root_path}</div>
                      <div>{t('dashboard.lastTab')}: {t(`workspace.tabs.${item.lastTab}`)}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
              <FolderIcon className="h-4 w-4" />
              {t('dashboard.quickStartTitle')}
            </div>
            <div className="mt-4 space-y-2">
              <button
                type="button"
                onClick={onAddProjectClick}
                className="flex w-full items-center gap-3 rounded-xl bg-gray-50 px-4 py-3 text-left text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
                data-name="projects-dashboard-create-card-action"
              >
                <PlusIcon className="h-4 w-4 flex-none" />
                {t('dashboard.quickActionCreate')}
              </button>
              <button
                type="button"
                onClick={onManageClick}
                className="flex w-full items-center gap-3 rounded-xl bg-gray-50 px-4 py-3 text-left text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
                data-name="projects-dashboard-manage-card-action"
              >
                <WrenchScrewdriverIcon className="h-4 w-4 flex-none" />
                {t('dashboard.quickActionManage')}
              </button>
            </div>
          </section>

        </div>
      </section>
    </div>
  );
};
