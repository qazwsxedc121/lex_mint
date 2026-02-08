/**
 * TTS Settings - Configuration-driven settings page
 */

import React from 'react';
import { ConfigSettingsPage } from './components/config';
import { ttsConfig } from './config';

export const TTSSettings: React.FC = () => {
  return (
    <ConfigSettingsPage
      config={ttsConfig}
    />
  );
};
