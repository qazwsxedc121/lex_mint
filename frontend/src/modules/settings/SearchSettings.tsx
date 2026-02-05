/**
 * Search Settings - Configuration-driven settings page
 *
 * This page is now powered by searchConfig, reducing boilerplate
 * from 195 lines to just ~15 lines.
 */

import React from 'react';
import { ConfigSettingsPage } from './components/config';
import { searchConfig } from './config';

export const SearchSettings: React.FC = () => {
  return <ConfigSettingsPage config={searchConfig} />;
};
