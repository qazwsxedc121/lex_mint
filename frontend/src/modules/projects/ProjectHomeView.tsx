import React, { useEffect, useMemo } from 'react';
import { FolderIcon, FolderOpenIcon, Cog6ToothIcon } from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import type { ProjectsOutletContext } from './workspace';
import { getProjectWorkspacePath } from './workspace';

type ProjectHomeContext = ProjectsOutletContext & {
  currentProject?: {
    id: string;
    name: string;
    description?: string | null;
    root_path: string;
  };
  onCloseProject?: () => void;
};

export const ProjectHomeView: React.FC = () => {
  const { t } = useTranslation('projects');
  const navigate = useNavigate();
  const { projectId } = useParams();
  const { projects, projectsLoading = false, onManageClick, onAddProjectClick, currentProject, onCloseProject } =
    useOutletContext<ProjectHomeContext>();
  const { currentProjectId, getProjectTab, setCurrentProject } = useProjectWorkspaceStore();

  useEffect(() => {
    if (projectId || !currentProjectId) {
      return;
    }
    const exists = projects.some((project) => project.id === currentProjectId);
    if (!exists) {
      return;
    }
    navigate(getProjectWorkspacePath(currentProjectId, getProjectTab(currentProjectId)), { replace: true });
  }, [currentProjectId, getProjectTab, navigate, projectId, projects]);

  const orderedProjects = useMemo(() => {
    const currentId = currentProject?.id || currentProjectId || null;
    return [...projects].sort((a, b) => {
      if (currentId) {
        if (a.id === currentId) {
          return -1;
        }
        if (b.id === currentId) {
          return 1;
        }
      }
      return a.name.localeCompare(b.name);
    });
  }, [currentProject?.id, currentProjectId, projects]);

  const handleProjectSelect = (nextProjectId: string) => {
    setCurrentProject(nextProjectId);
    navigate(getProjectWorkspacePath(nextProjectId, getProjectTab(nextProjectId)));
  };

  return (
    <div data-name="project-home-view" className="flex h-full min-h-0 flex-col overflow-auto bg-gray-50 px-4 py-4 dark:bg-gray-950">
      {!projectId && (
        <div className="mb-4 border-b border-gray-200 pb-3 dark:border-gray-800">
          <div className="inline-flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-sm font-medium text-blue-700 shadow-sm ring-1 ring-blue-100 dark:bg-gray-900 dark:text-blue-200 dark:ring-blue-900/40">
            <FolderIcon className="h-4 w-4" />
            {t('workspace.tabs.project')}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900" data-name="project-home-primary-card">
          <div className="flex items-start gap-4">
            <div className="rounded-2xl bg-blue-50 p-3 text-blue-700 dark:bg-blue-900/30 dark:text-blue-200">
              <FolderOpenIcon className="h-6 w-6" />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                {currentProject ? currentProject.name : t('workspace.project.emptyTitle')}
              </h2>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
                {currentProject
                  ? (currentProject.description?.trim() || t('workspace.project.currentDescription'))
                  : t('workspace.project.emptyDescription')}
              </p>
              {currentProject && (
                <div className="mt-3 rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-600 dark:bg-gray-950 dark:text-gray-300">
                  {currentProject.root_path}
                </div>
              )}
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={onAddProjectClick}
              className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              data-name="project-home-add-project"
            >
              {t('welcome.addProject')}
            </button>
            <button
              type="button"
              onClick={onManageClick}
              className="rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-800 hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:hover:bg-gray-800"
              data-name="project-home-manage-projects"
            >
              {t('welcome.manageProjects')}
            </button>
            {currentProject && onCloseProject && (
              <button
                type="button"
                onClick={onCloseProject}
                className="rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300 dark:hover:bg-red-950/50"
                data-name="project-home-close-project"
              >
                {t('selector.closeProject')}
              </button>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900" data-name="project-home-side-card">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
            <Cog6ToothIcon className="h-4 w-4" />
            {t('workspace.project.actionsTitle')}
          </div>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
            {currentProject ? t('workspace.project.actionsDescription') : t('workspace.project.emptyActionsDescription')}
          </p>
          {currentProject && (
            <div className="mt-4 space-y-2 text-sm text-gray-700 dark:text-gray-200">
              <div className="rounded-xl bg-gray-50 px-3 py-2 dark:bg-gray-950">
                {t('workspace.project.currentProjectLabel')}: {currentProject.name}
              </div>
              <div className="rounded-xl bg-gray-50 px-3 py-2 dark:bg-gray-950">
                {t('workspace.project.nextStepHint')}
              </div>
            </div>
          )}
        </section>
      </div>

      <section className="mt-4 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900" data-name="project-home-project-list">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('workspace.project.listTitle')}</h3>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{t('workspace.project.listDescription')}</p>
          </div>
          <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-300">
            {orderedProjects.length}
          </span>
        </div>

        <div className="mt-4">
          {projectsLoading ? (
            <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-300">
              {t('explorer.loading')}
            </div>
          ) : orderedProjects.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 px-4 py-8 text-center text-sm text-gray-600 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-300">
              {t('welcome.noProjects')}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {orderedProjects.map((project) => {
                const isActive = currentProject?.id === project.id;
                return (
                  <button
                    key={project.id}
                    type="button"
                    onClick={() => handleProjectSelect(project.id)}
                    className={`rounded-2xl border p-4 text-left transition ${
                      isActive
                        ? 'border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-950/30'
                        : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50 dark:border-gray-800 dark:bg-gray-900 dark:hover:border-gray-700 dark:hover:bg-gray-950/40'
                    }`}
                    data-name="project-home-project-item"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-gray-900 dark:text-gray-100">
                          {project.name}
                        </div>
                        {project.description && (
                          <div className="mt-1 line-clamp-2 text-sm text-gray-600 dark:text-gray-300">
                            {project.description}
                          </div>
                        )}
                      </div>
                      {isActive && (
                        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-200">
                          {t('workspace.project.currentBadge')}
                        </span>
                      )}
                    </div>
                    <div className="mt-3 truncate text-xs text-gray-500 dark:text-gray-400">{project.root_path}</div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </section>
    </div>
  );
};
