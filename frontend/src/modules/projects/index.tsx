/**
 * Projects Module - Entry point for projects module
 */

import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { ProjectManagement } from './components/ProjectManagement';
import { useProjects } from './hooks/useProjects';

export const ProjectsModule: React.FC = () => {
  const [showManagement, setShowManagement] = useState(false);
  const { projects, createProject, updateProject, deleteProject } = useProjects();

  return (
    <div className="flex h-screen overflow-hidden">
      <Outlet context={{
        projects,
        onManageClick: () => setShowManagement(true)
      }} />

      {showManagement && (
        <ProjectManagement
          projects={projects}
          onCreateProject={createProject}
          onUpdateProject={updateProject}
          onDeleteProject={deleteProject}
          onClose={() => setShowManagement(false)}
        />
      )}
    </div>
  );
};
