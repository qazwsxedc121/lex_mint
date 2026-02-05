/**
 * Webpage Settings Component
 *
 * Allows users to configure webpage fetch and proxy settings.
 */
import React, { useEffect, useState } from 'react';
import {
  getWebpageConfig,
  updateWebpageConfig
} from '../../services/api';

export const WebpageSettings: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [enabled, setEnabled] = useState(true);
  const [maxUrls, setMaxUrls] = useState(2);
  const [timeoutSeconds, setTimeoutSeconds] = useState(10);
  const [maxBytes, setMaxBytes] = useState(3_000_000);
  const [maxContentChars, setMaxContentChars] = useState(20_000);
  const [userAgent, setUserAgent] = useState('');
  const [proxy, setProxy] = useState('');
  const [trustEnv, setTrustEnv] = useState(true);
  const [diagnosticsEnabled, setDiagnosticsEnabled] = useState(true);
  const [diagnosticsTimeout, setDiagnosticsTimeout] = useState(2);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      setError(null);
      const config = await getWebpageConfig();
      setEnabled(config.enabled);
      setMaxUrls(config.max_urls);
      setTimeoutSeconds(config.timeout_seconds);
      setMaxBytes(config.max_bytes);
      setMaxContentChars(config.max_content_chars);
      setUserAgent(config.user_agent || '');
      setProxy(config.proxy || '');
      setTrustEnv(config.trust_env);
      setDiagnosticsEnabled(config.diagnostics_enabled);
      setDiagnosticsTimeout(config.diagnostics_timeout_seconds);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load configuration');
      console.error('Failed to load webpage settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      setSuccessMessage(null);

      await updateWebpageConfig({
        enabled,
        max_urls: maxUrls,
        timeout_seconds: timeoutSeconds,
        max_bytes: maxBytes,
        max_content_chars: maxContentChars,
        user_agent: userAgent.trim() || 'agent_dev/1.0',
        proxy: proxy.trim() ? proxy.trim() : null,
        trust_env: trustEnv,
        diagnostics_enabled: diagnosticsEnabled,
        diagnostics_timeout_seconds: diagnosticsTimeout,
      });

      setSuccessMessage('Settings saved successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
      await loadConfig();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
      console.error('Failed to save webpage settings:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div data-name="webpage-settings-loading" className="flex items-center justify-center h-64">
        <div className="text-gray-500 dark:text-gray-400">Loading webpage settings...</div>
      </div>
    );
  }

  return (
    <div data-name="webpage-settings-root" className="space-y-6">
      <div>
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
          Webpage Settings
        </h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Configure webpage fetching, proxy routing, and diagnostics.
        </p>
      </div>

      {error && (
        <div data-name="webpage-settings-error" className="rounded-md bg-red-50 dark:bg-red-900/20 p-4 border border-red-200 dark:border-red-800">
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {successMessage && (
        <div data-name="webpage-settings-success" className="rounded-md bg-green-50 dark:bg-green-900/20 p-4 border border-green-200 dark:border-green-800">
          <p className="text-sm text-green-800 dark:text-green-200">{successMessage}</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div data-name="webpage-settings-basic" className="space-y-6 rounded-lg border border-gray-200 dark:border-gray-700 p-5 bg-white dark:bg-gray-800">
          <div className="flex items-start gap-3">
            <input
              id="webpage-enabled"
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded"
            />
            <div>
              <label htmlFor="webpage-enabled" className="block text-sm font-medium text-gray-900 dark:text-white">
                Enable webpage parsing
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Extract URLs from chat input and fetch content for grounding.
              </p>
            </div>
          </div>

          <div>
            <label htmlFor="max-urls" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              Max URLs
            </label>
            <input
              id="max-urls"
              type="number"
              min="1"
              max="10"
              value={maxUrls}
              onChange={(e) => setMaxUrls(parseInt(e.target.value, 10) || 1)}
              className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Maximum URLs to fetch per message (1 - 10).
            </p>
          </div>

          <div>
            <label htmlFor="timeout-seconds" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              Timeout (seconds)
            </label>
            <input
              id="timeout-seconds"
              type="number"
              min="2"
              max="120"
              value={timeoutSeconds}
              onChange={(e) => setTimeoutSeconds(parseInt(e.target.value, 10) || 2)}
              className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Total request timeout (2 - 120 seconds).
            </p>
          </div>

          <div>
            <label htmlFor="max-bytes" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              Max Bytes
            </label>
            <input
              id="max-bytes"
              type="number"
              min="100000"
              max="20000000"
              value={maxBytes}
              onChange={(e) => setMaxBytes(parseInt(e.target.value, 10) || 100000)}
              className="w-48 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Maximum response bytes to read (100,000 - 20,000,000).
            </p>
          </div>

          <div>
            <label htmlFor="max-content-chars" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              Max Content Chars
            </label>
            <input
              id="max-content-chars"
              type="number"
              min="500"
              max="200000"
              value={maxContentChars}
              onChange={(e) => setMaxContentChars(parseInt(e.target.value, 10) || 500)}
              className="w-48 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Max characters passed to the assistant (500 - 200,000).
            </p>
          </div>
        </div>

        <div data-name="webpage-settings-proxy" className="space-y-6 rounded-lg border border-gray-200 dark:border-gray-700 p-5 bg-white dark:bg-gray-800">
          <div>
            <label htmlFor="proxy" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              Proxy URL
            </label>
            <input
              id="proxy"
              type="text"
              value={proxy}
              onChange={(e) => setProxy(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="http://127.0.0.1:7897"
            />
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Leave empty to disable explicit proxy routing.
            </p>
          </div>

          <div className="flex items-start gap-3">
            <input
              id="trust-env"
              type="checkbox"
              checked={trustEnv}
              onChange={(e) => setTrustEnv(e.target.checked)}
              className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded"
            />
            <div>
              <label htmlFor="trust-env" className="block text-sm font-medium text-gray-900 dark:text-white">
                Trust environment proxies
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Read HTTP_PROXY/HTTPS_PROXY from environment variables.
              </p>
            </div>
          </div>

          <div>
            <label htmlFor="user-agent" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              User Agent
            </label>
            <input
              id="user-agent"
              type="text"
              value={userAgent}
              onChange={(e) => setUserAgent(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="Mozilla/5.0 ..."
            />
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Override the User-Agent header for webpage requests.
            </p>
          </div>

          <div className="flex items-start gap-3">
            <input
              id="diagnostics-enabled"
              type="checkbox"
              checked={diagnosticsEnabled}
              onChange={(e) => setDiagnosticsEnabled(e.target.checked)}
              className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded"
            />
            <div>
              <label htmlFor="diagnostics-enabled" className="block text-sm font-medium text-gray-900 dark:text-white">
                Enable diagnostics
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Add DNS/TCP/TLS info to error messages.
              </p>
            </div>
          </div>

          <div>
            <label htmlFor="diagnostics-timeout" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              Diagnostics Timeout (seconds)
            </label>
            <input
              id="diagnostics-timeout"
              type="number"
              min="0.5"
              max="5"
              step="0.5"
              value={diagnosticsTimeout}
              onChange={(e) => setDiagnosticsTimeout(parseFloat(e.target.value) || 0.5)}
              className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Timeout for diagnostic DNS/TCP checks (0.5 - 5 seconds).
            </p>
          </div>
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
