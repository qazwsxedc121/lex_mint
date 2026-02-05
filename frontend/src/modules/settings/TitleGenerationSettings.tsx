/**
 * Title Generation Settings - Configuration-driven settings page
 *
 * This page is now powered by titleGenerationConfig, reducing boilerplate
 * from 271 lines to just ~20 lines.
 */

import React from 'react';
import { ConfigSettingsPage } from './components/config';
import { titleGenerationConfig } from './config';
import { useModels } from './hooks/useModels';

export const TitleGenerationSettings: React.FC = () => {
  const modelsHook = useModels();

  return (
    <ConfigSettingsPage
      config={titleGenerationConfig}
      context={{ models: modelsHook.models }}
    />
  );
};
