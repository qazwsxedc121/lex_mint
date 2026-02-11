/**
 * Projects Module - Entry point for projects module
 */

import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { ProjectManagement } from './components/ProjectManagement';
import { useProjects } from './hooks/useProjects';

type ManagementMode = 'manage' | 'create';

export const ProjectsModule: React.FC = () => {
  const [showManagement, setShowManagement] = useState(false);
  const [managementMode, setManagementMode] = useState<ManagementMode>('manage');
  const { projects, createProject, updateProject, deleteProject } = useProjects();

  const openManagement = () => {
    setManagementMode('manage');
    setShowManagement(true);
  };

  const openCreateProject = () => {
    setManagementMode('create');
    setShowManagement(true);
  };

  return (
    <div data-name="projects-module-root" className="flex flex-1 overflow-hidden min-w-0">
      <Outlet context={{
        projects,
        onManageClick: openManagement,
        onAddProjectClick: openCreateProject,
      }} />

      {showManagement && (
        <ProjectManagement
          projects={projects}
          onCreateProject={createProject}
          onUpdateProject={updateProject}
          onDeleteProject={deleteProject}
          initialCreateForm={managementMode === 'create'}
          onClose={() => setShowManagement(false)}
        />
      )}
    </div>
  );
};
