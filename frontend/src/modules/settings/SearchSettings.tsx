/**
 * Search Settings Component
 *
 * Allows users to configure web search provider settings.
 */
import React, { useEffect, useState } from 'react';
import {
  getSearchConfig,
  updateSearchConfig
} from '../../services/api';

type ProviderOption = {
  value: string;
  label: string;
  description: string;
};

const PROVIDER_OPTIONS: ProviderOption[] = [
  {
    value: 'duckduckgo',
    label: 'DuckDuckGo',
    description: 'Free, no API key required'
  },
  {
    value: 'tavily',
    label: 'Tavily',
    description: 'Higher quality, requires API key in config/keys_config.yaml'
  }
];

export const SearchSettings: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [provider, setProvider] = useState('duckduckgo');
  const [maxResults, setMaxResults] = useState(6);
  const [timeoutSeconds, setTimeoutSeconds] = useState(10);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      setError(null);
      const config = await getSearchConfig();
      setProvider(config.provider || 'duckduckgo');
      setMaxResults(config.max_results);
      setTimeoutSeconds(config.timeout_seconds);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load configuration');
      console.error('Failed to load search settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      setSuccessMessage(null);

      await updateSearchConfig({
        provider,
        max_results: maxResults,
        timeout_seconds: timeoutSeconds
      });

      setSuccessMessage('Settings saved successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
      await loadConfig();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
      console.error('Failed to save search settings:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div data-name="search-settings-loading" className="flex items-center justify-center h-64">
        <div className="text-gray-500 dark:text-gray-400">Loading search settings...</div>
      </div>
    );
  }

  return (
    <div data-name="search-settings-root" className="space-y-6">
      <div>
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
          Search Settings
        </h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Choose a search provider for the chat web search toggle.
        </p>
      </div>

      {error && (
        <div data-name="search-settings-error" className="rounded-md bg-red-50 dark:bg-red-900/20 p-4 border border-red-200 dark:border-red-800">
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {successMessage && (
        <div data-name="search-settings-success" className="rounded-md bg-green-50 dark:bg-green-900/20 p-4 border border-green-200 dark:border-green-800">
          <p className="text-sm text-green-800 dark:text-green-200">{successMessage}</p>
        </div>
      )}

      <div className="space-y-6">
        <div>
          <label htmlFor="provider" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
            Search Provider
          </label>
          <select
            id="provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="max-w-md block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          >
            {PROVIDER_OPTIONS.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {PROVIDER_OPTIONS.find(option => option.value === provider)?.description}
          </p>
        </div>

        <div>
          <label htmlFor="max-results" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
            Max Results
          </label>
          <input
            id="max-results"
            type="number"
            min="1"
            max="20"
            value={maxResults}
            onChange={(e) => setMaxResults(parseInt(e.target.value, 10) || 1)}
            className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          />
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Number of sources returned to the assistant (1 - 20).
          </p>
        </div>

        <div>
          <label htmlFor="timeout" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
            Timeout (seconds)
          </label>
          <input
            id="timeout"
            type="number"
            min="5"
            max="60"
            value={timeoutSeconds}
            onChange={(e) => setTimeoutSeconds(parseInt(e.target.value, 10) || 5)}
            className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          />
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Maximum time to wait for search results (5 - 60 seconds).
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
        <button
          type="button"
          onClick={loadConfig}
          disabled={saving}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Reload
        </button>
      </div>
    </div>
  );
};
