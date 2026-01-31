/**
 * Title Generation Settings Component
 *
 * Allows users to configure automatic title generation for conversations.
 */
import React, { useState, useEffect } from 'react';
import {
  getTitleGenerationConfig,
  updateTitleGenerationConfig,
  listModels
} from '../../services/api';
import type { Model } from '../../types/model';

export const TitleGenerationSettings: React.FC = () => {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Form state
  const [enabled, setEnabled] = useState(true);
  const [triggerThreshold, setTriggerThreshold] = useState(1);
  const [modelId, setModelId] = useState('');
  const [promptTemplate, setPromptTemplate] = useState('');
  const [maxContextRounds, setMaxContextRounds] = useState(3);
  const [timeoutSeconds, setTimeoutSeconds] = useState(10);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load config and models in parallel
      const [configData, modelsData] = await Promise.all([
        getTitleGenerationConfig(),
        listModels()
      ]);

      setModels(modelsData);

      // Set form values
      setEnabled(configData.enabled);
      setTriggerThreshold(configData.trigger_threshold);
      setModelId(configData.model_id);
      setPromptTemplate(configData.prompt_template);
      setMaxContextRounds(configData.max_context_rounds);
      setTimeoutSeconds(configData.timeout_seconds);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load configuration');
      console.error('Failed to load title generation settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      setSuccessMessage(null);

      const updates = {
        enabled,
        trigger_threshold: triggerThreshold,
        model_id: modelId,
        prompt_template: promptTemplate,
        max_context_rounds: maxContextRounds,
        timeout_seconds: timeoutSeconds
      };

      await updateTitleGenerationConfig(updates);

      setSuccessMessage('Settings saved successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);

      // Reload to confirm
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
      console.error('Failed to save title generation settings:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500 dark:text-gray-400">Loading title generation settings...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
          Title Generation Settings
        </h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Configure automatic conversation title generation using a small language model.
        </p>
      </div>

      {/* Error message */}
      {error && (
        <div className="rounded-md bg-red-50 dark:bg-red-900/20 p-4 border border-red-200 dark:border-red-800">
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {/* Success message */}
      {successMessage && (
        <div className="rounded-md bg-green-50 dark:bg-green-900/20 p-4 border border-green-200 dark:border-green-800">
          <p className="text-sm text-green-800 dark:text-green-200">{successMessage}</p>
        </div>
      )}

      {/* Form */}
      <div className="space-y-6">
        {/* Enabled toggle */}
        <div className="flex items-start">
          <div className="flex items-center h-5">
            <input
              id="enabled"
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
          </div>
          <div className="ml-3">
            <label htmlFor="enabled" className="font-medium text-gray-900 dark:text-white cursor-pointer">
              Enable automatic title generation
            </label>
          </div>
        </div>

        {/* Trigger threshold */}
        <div>
          <label htmlFor="threshold" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
            Trigger Threshold (conversation rounds)
          </label>
          <input
            id="threshold"
            type="number"
            min="1"
            max="10"
            value={triggerThreshold}
            onChange={(e) => setTriggerThreshold(parseInt(e.target.value) || 1)}
            disabled={!enabled}
            className="w-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500 dark:disabled:text-gray-500"
          />
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Generate title after this many conversation rounds (1 round = user message + assistant response)
          </p>
        </div>

        {/* Model selection */}
        <div>
          <label htmlFor="model" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
            Small Model for Title Generation
          </label>
          <select
            id="model"
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            disabled={!enabled}
            className="max-w-lg block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500 dark:disabled:text-gray-500"
          >
            <option value="">Select a model...</option>
            {models.map((model) => {
              // Build composite model ID: provider_id:model_id
              const compositeId = `${model.provider_id}:${model.id}`;
              return (
                <option key={compositeId} value={compositeId}>
                  {model.name || model.id}
                </option>
              );
            })}
          </select>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Recommended: Use a small, fast model like GPT-4o-mini to minimize cost
          </p>
        </div>

        {/* Max context rounds */}
        <div>
          <label htmlFor="context" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
            Max Context Rounds
          </label>
          <input
            id="context"
            type="number"
            min="1"
            max="10"
            value={maxContextRounds}
            onChange={(e) => setMaxContextRounds(parseInt(e.target.value) || 3)}
            disabled={!enabled}
            className="w-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500 dark:disabled:text-gray-500"
          />
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Maximum number of recent conversation rounds to use as context
          </p>
        </div>

        {/* Timeout */}
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
            onChange={(e) => setTimeoutSeconds(parseInt(e.target.value) || 10)}
            disabled={!enabled}
            className="w-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500 dark:disabled:text-gray-500"
          />
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Maximum time to wait for title generation
          </p>
        </div>

        {/* Prompt template */}
        <div>
          <label htmlFor="prompt" className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
            Prompt Template
          </label>
          <textarea
            id="prompt"
            value={promptTemplate}
            onChange={(e) => setPromptTemplate(e.target.value)}
            rows={6}
            disabled={!enabled}
            placeholder="Enter prompt template. Use {conversation_text} as placeholder for conversation content."
            className="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 font-mono text-sm disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500 dark:disabled:text-gray-500"
          />
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Use <code className="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs">{'{conversation_text}'}</code> as a placeholder for the actual conversation content
          </p>
        </div>

        {/* Save button */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving || !enabled}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
          {!enabled && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Enable automatic title generation to save settings
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
