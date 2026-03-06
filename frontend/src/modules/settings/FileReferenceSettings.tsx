/**
 * File Reference Settings - Configuration-driven settings page.
 */

import React from 'react';
import { ConfigSettingsPage } from './components/config';
import { fileReferenceConfig } from './config/fileReference.config';
import { ensureFileReferencePreviewConfigLoaded } from '../../shared/chat/config/fileReferencePreview';
import { API_BASE } from '../../services/apiBase';

export const FileReferenceSettings: React.FC = () => {
  const apiClient = {
    get: async (url: string) => {
      const response = await fetch(`${API_BASE}${url}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response.json();
    },
    post: async (url: string, data: unknown) => {
      const response = await fetch(`${API_BASE}${url}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const result = await response.json();
      // Refresh shared runtime preview limits immediately after save.
      await ensureFileReferencePreviewConfigLoaded(true);
      return result;
    },
  };

  return <ConfigSettingsPage config={fileReferenceConfig} apiClient={apiClient} />;
};
