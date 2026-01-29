/**
 * ModelsPage - Wrapper for ModelList with data loading
 */

import React from 'react';
import { ModelList } from './components/ModelList';
import { useModels } from './hooks/useModels';

export const ModelsPage: React.FC = () => {
  const modelsHook = useModels();

  if (modelsHook.loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  if (modelsHook.error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500">{modelsHook.error}</div>
      </div>
    );
  }

  return <ModelList {...modelsHook} />;
};
