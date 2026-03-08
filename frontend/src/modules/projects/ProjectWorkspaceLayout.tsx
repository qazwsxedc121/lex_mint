import React, { useCallback, useEffect, useMemo } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import type { ProjectsOutletContext } from './workspace';
import { PROJECT_WORKSPACE_TABS, getProjectWorkspacePath, isProjectWorkspaceTab } from './workspace';

export const ProjectWorkspaceLayout: React.FC = () => {
  const { t } = useTranslation('projects');
  const { projectId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { projects, projectsLoading = false, onManageClick, onAddProjectClick } = useOutletContext<ProjectsOutletContext>();
  const { setCurrentProject, setProjectTab } = useProjectWorkspaceStore();

  const currentProject = useMemo(
    () => projects.find((project) => project.id === projectId),
    [projectId, projects]
  );

  useEffect(() => {
    if (projectId) {
      setCurrentProject(projectId);
    }
  }, [projectId, setCurrentProject]);

  useEffect(() => {
    if (!projectId) {
      return;
    }
    const parts = location.pathname.split('/');
    const maybeTab = parts[parts.length - 1] || null;
    if (!isProjectWorkspaceTab(maybeTab)) {
      return;
    }
    setProjectTab(projectId, maybeTab);
  }, [location.pathname, projectId, setProjectTab]);

  const handleCloseProject = useCallback(() => {
    setCurrentProject(null);
    navigate('/projects', { replace: true });
  }, [navigate, setCurrentProject]);

  if (!projectId) {
    return (
      <div className="flex flex-1 items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400">{t('explorer.invalidId')}</p>
          <button
            type="button"
            onClick={onAddProjectClick}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {t('welcome.addProject')}
          </button>
        </div>
      </div>
    );
  }

  if (!currentProject && projectsLoading) {
    return (
      <div className="flex flex-1 items-center justify-center bg-white dark:bg-gray-900">
        <p className="text-gray-500 dark:text-gray-400">{t('explorer.loading')}</p>
      </div>
    );
  }

  if (!currentProject) {
    return (
      <div className="flex flex-1 items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400">{t('explorer.invalidId')}</p>
          <button
            type="button"
            onClick={onAddProjectClick}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {t('welcome.addProject')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div data-name="project-workspace-layout" className="flex min-w-0 flex-1 flex-col overflow-hidden bg-white dark:bg-gray-900">
      <div className="border-b border-gray-200 bg-white px-4 dark:border-gray-700 dark:bg-gray-900" data-name="project-workspace-tabs">
        <nav className="flex items-center gap-2 overflow-x-auto py-2">
          {PROJECT_WORKSPACE_TABS.map((tab) => (
            <NavLink
              key={tab}
              to={getProjectWorkspacePath(projectId, tab)}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-800 dark:hover:text-white'
                }`
              }
              data-name={`project-workspace-tab-${tab}`}
            >
              {t(`workspace.tabs.${tab}`)}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Outlet
          context={{
            projectId,
            currentProject,
            projects,
            onManageClick,
            onAddProjectClick,
            onCloseProject: handleCloseProject,
          }}
        />
      </div>
    </div>
  );
};
