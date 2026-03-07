import React from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import { getProjectWorkspacePath } from './workspace';

export const ProjectTabRedirect: React.FC = () => {
  const { projectId } = useParams();
  const { getProjectTab } = useProjectWorkspaceStore();

  if (!projectId) {
    return <Navigate to="/projects" replace />;
  }

  return <Navigate to={getProjectWorkspacePath(projectId, getProjectTab(projectId))} replace />;
};
