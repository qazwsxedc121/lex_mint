/**
 * Follow-up Questions Settings - Configuration-driven settings page
 *
 * This page is powered by followupConfig for consistent styling and behavior.
 */

import React from 'react';
import { ConfigSettingsPage } from './components/config';
import { followupConfig } from './config';
import { useModels } from './hooks/useModels';

export const FollowupSettings: React.FC = () => {
  const modelsHook = useModels();

  return (
    <ConfigSettingsPage
      config={followupConfig}
      context={{ models: modelsHook.models }}
    />
  );
};
