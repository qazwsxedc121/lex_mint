/**
 * Translation Settings - Configuration-driven settings page
 */

import React from 'react';
import { ConfigSettingsPage } from './components/config';
import { translationConfig } from './config';
import { useModels } from './hooks/useModels';

export const TranslationSettings: React.FC = () => {
  const modelsHook = useModels();

  return (
    <ConfigSettingsPage
      config={translationConfig}
      context={{ models: modelsHook.models }}
    />
  );
};
