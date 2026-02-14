/**
 * ConfigSettingsPage Component
 *
 * Main config page renderer for simple configuration pages.
 * Handles loading, saving, and displaying configuration forms.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { PageHeader, LoadingSpinner, ErrorMessage, SuccessMessage } from '../common';
import { ConfigForm } from './ConfigForm';
import type { SimpleConfigSettingsConfig, ConfigContext } from '../../config/types';

interface ConfigSettingsPageProps {
  /** Page configuration */
  config: SimpleConfigSettingsConfig;
  /** Additional context for dynamic options */
  context?: ConfigContext;
  /** API client (defaults to fetch) */
  apiClient?: {
    get: (url: string) => Promise<any>;
    post: (url: string, data: any) => Promise<any>;
  };
}

export const ConfigSettingsPage: React.FC<ConfigSettingsPageProps> = ({
  config,
  context = {},
  apiClient
}) => {
  const [formData, setFormData] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const { t } = useTranslation('settings');

  // Default API client using fetch
  const API_BASE = import.meta.env.VITE_API_URL;
  if (!API_BASE) {
    throw new Error('VITE_API_URL is not configured. Set API_PORT in the root .env file.');
  }

  const defaultApiClient = {
    get: async (url: string) => {
      const response = await fetch(`${API_BASE}${url}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response.json();
    },
    post: async (url: string, data: any) => {
      const response = await fetch(`${API_BASE}${url}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response.json();
    }
  };

  const api = apiClient || defaultApiClient;

  // Load configuration
  const loadConfig = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const data = await api.get(config.apiEndpoint.get);

      // Transform data if needed
      const transformed = config.transformLoad ? config.transformLoad(data) : data;

      // Initialize form data with defaults
      const initialData: any = { ...transformed };
      config.fields.forEach((field) => {
        if (initialData[field.name] === undefined && 'defaultValue' in field) {
          initialData[field.name] = field.defaultValue;
        }
      });

      setFormData(initialData);
    } catch (err) {
      const message = err instanceof Error ? err.message : t('config.failedToLoad');
      setError(message);
      console.error('Failed to load config:', err);
    } finally {
      setLoading(false);
    }
  }, [api, config, t]);

  // Initial load
  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  // Handle form submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setShowErrors(true);

    // Validate form
    if (config.validateForm) {
      const error = config.validateForm(formData);
      if (error) {
        alert(error);
        return;
      }
    }

    // Check required fields
    for (const field of config.fields) {
      if (field.required && !formData[field.name]) {
        alert(t('crud.requiredField', { field: field.label }));
        return;
      }

      // Run custom validation
      if (field.validate) {
        const error = field.validate(formData[field.name]);
        if (error) {
          alert(t('crud.fieldError', { field: field.label, error }));
          return;
        }
      }
    }

    try {
      setSaving(true);
      setError(null);
      setSuccessMessage(null);

      // Transform data if needed
      const dataToSave = config.transformSave ? config.transformSave(formData) : formData;

      await api.post(config.apiEndpoint.update, dataToSave);

      setSuccessMessage(t('config.savedSuccess'));
      setTimeout(() => setSuccessMessage(null), 3000);

      // Reload to confirm
      await loadConfig();
      setShowErrors(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : t('config.failedToSave');
      setError(message);
      console.error('Failed to save config:', err);
    } finally {
      setSaving(false);
    }
  };

  // Render loading state
  if (loading) {
    return config.loadingState || (
      <LoadingSpinner message={t('config.loadingSettings')} />
    );
  }

  return (
    <div className="space-y-6" data-name="config-settings-page">
      {/* Page Header */}
      <PageHeader
        title={config.title}
        description={config.description}
        actions={
          config.customActions?.map((action, index) => (
            <button
              key={index}
              onClick={() => action.onClick(formData, context)}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md ${
                action.variant === 'danger'
                  ? 'text-white bg-red-600 hover:bg-red-700'
                  : action.variant === 'secondary'
                  ? 'text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600'
                  : 'text-white bg-blue-600 hover:bg-blue-700'
              }`}
            >
              {action.icon && <action.icon className="h-4 w-4" />}
              {action.label}
            </button>
          ))
        }
      />

      {/* Success Message */}
      {successMessage && (
        <SuccessMessage
          message={successMessage}
          onDismiss={() => setSuccessMessage(null)}
        />
      )}

      {/* Error Message */}
      {error && (
        <ErrorMessage
          message={error}
          onRetry={loadConfig}
        />
      )}

      {/* Form */}
      {!error && (
        <ConfigForm
          fields={config.fields}
          formData={formData}
          onChange={setFormData}
          onSubmit={handleSubmit}
          context={context}
          showErrors={showErrors}
          isSubmitting={saving}
        />
      )}
    </div>
  );
};
