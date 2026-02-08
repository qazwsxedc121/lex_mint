/**
 * RAG Settings - Configuration-driven settings page
 */

import React from 'react';
import { ConfigSettingsPage } from './components/config';
import { ragConfig } from './config';

export const RagSettings: React.FC = () => {
  return <ConfigSettingsPage config={ragConfig} />;
};
