/**
 * Compression Settings - Configuration-driven settings page
 */

import React from 'react';
import { ConfigSettingsPage } from './components/config';
import { compressionConfig } from './config';
import { useModels } from './hooks/useModels';

export const CompressionSettings: React.FC = () => {
  const modelsHook = useModels();

  return (
    <ConfigSettingsPage
      config={compressionConfig}
      context={{ models: modelsHook.models }}
    />
  );
};
