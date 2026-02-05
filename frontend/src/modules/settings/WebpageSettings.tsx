/**
 * Webpage Settings - Configuration-driven settings page
 *
 * This page is now powered by webpageConfig, reducing boilerplate
 * from 323 lines to just ~15 lines.
 */

import React from 'react';
import { ConfigSettingsPage } from './components/config';
import { webpageConfig } from './config';

export const WebpageSettings: React.FC = () => {
  return <ConfigSettingsPage config={webpageConfig} />;
};
