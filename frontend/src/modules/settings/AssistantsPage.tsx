/**
 * AssistantsPage - Wrapper for AssistantList with data loading
 */

import React from 'react';
import { AssistantList } from './components/AssistantList';
import { useModels } from './hooks/useModels';
import { useAssistants } from './hooks/useAssistants';

export const AssistantsPage: React.FC = () => {
  const modelsHook = useModels();
  const assistantsHook = useAssistants();

  if (modelsHook.loading || assistantsHook.loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  if (modelsHook.error || assistantsHook.error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500">{modelsHook.error || assistantsHook.error}</div>
      </div>
    );
  }

  return (
    <AssistantList
      assistants={assistantsHook.assistants}
      defaultAssistantId={assistantsHook.defaultAssistantId}
      models={modelsHook.models}
      onCreateAssistant={assistantsHook.createAssistant}
      onUpdateAssistant={assistantsHook.updateAssistant}
      onDeleteAssistant={assistantsHook.deleteAssistant}
      onSetDefault={assistantsHook.setDefaultAssistant}
    />
  );
};
